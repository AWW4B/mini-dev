# FILE: src/asf/m5_shared/context/memory.py
# ROLE: Decision log and project memory with tag lookup and invalidation by source hash.
# ARCH REF: M5; p12 memory; D-32
# OWNS: Memory rows
# DOES NOT OWN: Conversation compaction (compaction.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (persistence)
#   - called by src/asf/m5_shared/context/context_service.py: ProjectMemory
#   - called by tests/m5_shared/context/test_memory.py: ProjectMemory
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/context/test_memory.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/context/memory.py` and `uv run mypy src/asf/m5_shared/context/memory.py` are clean.

import json
import logging
import sqlite3
import uuid
from typing import Any

from asf.m5_shared.state_store.store import StateStore

logger = logging.getLogger(__name__)


class ProjectMemory:
    store: StateStore | None
    _entries: list[dict[str, Any]]

    def __init__(self, store: StateStore | None = None) -> None:
        self.store = store
        self._entries = []
        if self.store is not None:
            self._init_db()
            self._load_from_db()

    def _init_db(self) -> None:
        if self.store is None:
            return
        with self.store.conn:
            self.store.conn.execute("""
                CREATE TABLE IF NOT EXISTS project_decisions (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    source_hashes TEXT NOT NULL,
                    valid INTEGER NOT NULL DEFAULT 1
                );
            """)

    def _load_from_db(self) -> None:
        if self.store is None:
            return
        try:
            cur = self.store.conn.execute("SELECT id, text, tags, source_hashes, valid FROM project_decisions")
            for row in cur.fetchall():
                self._entries.append({
                    "id": str(row[0]),
                    "text": str(row[1]),
                    "tags": json.loads(row[2]) if isinstance(row[2], str) else [],
                    "source_hashes": json.loads(row[3]) if isinstance(row[3], str) else {},
                    "valid": bool(row[4]),
                })
        except (sqlite3.Error, ValueError):
            logger.error("could not load the project decisions; starting with an empty memory", exc_info=True)

    def record_decision(self, text: str, tags: list[str], source_hashes: dict[str, str]) -> None:
        entry_id = str(uuid.uuid4())
        entry: dict[str, Any] = {
            "id": entry_id,
            "text": text,
            "tags": list(tags),
            "source_hashes": dict(source_hashes),
            "valid": True,
        }
        self._entries.append(entry)

        if self.store is not None:
            try:
                with self.store.conn:
                    self.store.conn.execute(
                        "INSERT INTO project_decisions (id, text, tags, source_hashes, valid) VALUES (?, ?, ?, ?, 1)",
                        (entry_id, text, json.dumps(tags), json.dumps(source_hashes)),
                    )
            except sqlite3.Error:
                logger.error("could not persist decision %s; it is kept in memory only", entry_id, exc_info=True)

    def relevant(self, tags: list[str], limit: int = 10) -> list[str]:
        req_tags = {t.lower() for t in tags}
        matches: list[tuple[int, str]] = []

        for e in reversed(self._entries):
            if not e.get("valid", True):
                continue
            if not req_tags or "*" in req_tags:
                matches.append((1, str(e["text"])))
            else:
                entry_tags = {t.lower() for t in e.get("tags", [])}
                common = len(req_tags & entry_tags)
                if common > 0:
                    matches.append((common, str(e["text"])))

        matches.sort(key=lambda x: x[0], reverse=True)
        return [text for _, text in matches[:limit]]

    def invalidate_changed(self, current_hashes: dict[str, str]) -> int:
        invalidated_count = 0
        for e in self._entries:
            if not e.get("valid", True):
                continue
            src_hashes: dict[str, str] = e.get("source_hashes", {})
            changed = False
            for path, old_hash in src_hashes.items():
                if path in current_hashes and current_hashes[path] != old_hash:
                    changed = True
                    break
            if changed:
                e["valid"] = False
                invalidated_count += 1
                if self.store is not None:
                    try:
                        with self.store.conn:
                            self.store.conn.execute(
                                "UPDATE project_decisions SET valid = 0 WHERE id = ?",
                                (e["id"],),
                            )
                    except sqlite3.Error:
                        logger.error("could not persist the invalidation of decision %s", e["id"], exc_info=True)

        return invalidated_count
