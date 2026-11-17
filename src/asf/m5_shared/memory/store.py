# FILE: src/asf/m5_shared/memory/store.py
# ROLE: Episodic, semantic, procedural and session memory in SQLite with dedupe, evidence counting, eviction, promotion and invalidation.
# ARCH REF: M5; p12 Context & Memory Service; docs/architecture/MEMORY_ARCHITECTURE.md
# OWNS: Memory rows and their lifecycle
# DOES NOT OWN: Choosing what enters a prompt (router.py); working memory (the prompt itself)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/memory/device_budget.py: pct (retention percentages)
#   - imports from src/asf/m5_shared/memory/lexical.py: Bm25, terms (search without FTS5)
#   - imports from src/asf/contracts/errors.py: ConfigError (invalid retention)
#   - called by tests/m5_shared/memory/test_store.py: MemoryRecord, MemoryStore, row_caps
#   - called by src/asf/m5_shared/memory/tree_rag.py: MemoryRecord, MemoryStore
#   - called by src/asf/m5_shared/memory/router.py: MemoryRecord, MemoryStore
#   - called by tests/m5_shared/memory/test_router.py: MemoryRecord, MemoryStore
#   - called by tests/m5_shared/memory/test_tree_rag.py: MemoryRecord, MemoryStore
#   - called by src/asf/m5_shared/memory/hooks.py: MemoryRecord, MemoryStore, open_memory_store, row_caps
#   - called by tests/m5_shared/memory/test_hooks.py: MemoryRecord
#   - called by src/asf/cli/commands/memory_cmd.py: open_memory_store, row_caps
#   - called by tests/cli/commands/test_memory_cmd.py: MemoryRecord, open_memory_store
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/memory/test_store.py pass on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/memory/store.py` and `uv run mypy src/asf/m5_shared/memory/store.py` are clean.

import functools
import hashlib
import json
import logging
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from asf.contracts.errors import ConfigError
from asf.m5_shared.memory.device_budget import pct
from asf.m5_shared.memory.lexical import Bm25, terms

logger = logging.getLogger(__name__)

StoredLayer = Literal["episodic", "semantic", "procedural", "session"]
STORED_LAYERS: tuple[StoredLayer, ...] = ("episodic", "semantic", "procedural", "session")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mem_records (
    id INTEGER PRIMARY KEY,
    layer TEXT NOT NULL,
    scope TEXT NOT NULL,
    topic TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    content_hash TEXT NOT NULL,
    source_hash TEXT,
    trusted INTEGER NOT NULL DEFAULT 1,
    run_id TEXT,
    task_id TEXT,
    runs TEXT NOT NULL DEFAULT '[]',
    helpful INTEGER NOT NULL DEFAULT 0,
    harmful INTEGER NOT NULL DEFAULT 0,
    created REAL NOT NULL,
    last_used REAL NOT NULL,
    uses INTEGER NOT NULL DEFAULT 0,
    UNIQUE (layer, scope, content_hash)
);
CREATE INDEX IF NOT EXISTS mem_records_layer ON mem_records (layer, scope, last_used);
CREATE INDEX IF NOT EXISTS mem_records_run ON mem_records (run_id, layer);
"""
_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS mem_fts USING fts5(title, text, tags, topic, content='mem_records', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS mem_ai AFTER INSERT ON mem_records BEGIN
    INSERT INTO mem_fts(rowid, title, text, tags, topic) VALUES (new.id, new.title, new.text, new.tags, new.topic);
END;
CREATE TRIGGER IF NOT EXISTS mem_ad AFTER DELETE ON mem_records BEGIN
    INSERT INTO mem_fts(mem_fts, rowid, title, text, tags, topic) VALUES ('delete', old.id, old.title, old.text, old.tags, old.topic);
END;
CREATE TRIGGER IF NOT EXISTS mem_au AFTER UPDATE OF title, text, tags, topic ON mem_records BEGIN
    INSERT INTO mem_fts(mem_fts, rowid, title, text, tags, topic) VALUES ('delete', old.id, old.title, old.text, old.tags, old.topic);
    INSERT INTO mem_fts(rowid, title, text, tags, topic) VALUES (new.id, new.title, new.text, new.tags, new.topic);
END;
"""


def _locked[T](method: Callable[..., T]) -> Callable[..., T]:
    """Attempts run on scheduler threads: every store operation holds the store's lock."""

    @functools.wraps(method)
    def wrapper(self: "MemoryStore", *args: Any, **kwargs: Any) -> T:
        with self.lock:
            return method(self, *args, **kwargs)

    return wrapper


class MemoryRecord(BaseModel):
    """One unit of long-lived memory. Working memory is never stored: it is the prompt being built."""

    id: int | None = None
    layer: StoredLayer
    scope: str = "project"              # "project" or "run:<run_id>"
    topic: str = ""                     # a path-like key: a file, a failure class, a skill; the tree is built from it
    title: str
    text: str
    tags: list[str] = Field(default_factory=list)
    source_hash: str | None = None      # semantic facts are invalidated when their source file changes
    trusted: bool = True                # False for anything that came from an MCP server or the web
    run_id: str | None = None
    task_id: str | None = None
    helpful: int = 0
    harmful: int = 0
    runs: list[str] = Field(default_factory=list)
    score: float = 0.0

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(f"{self.title}\n{self.text}".encode()).hexdigest()


def row_caps(disk_cap_mb: int, retention: dict[str, Any]) -> dict[str, int]:
    """Rows each stored layer may keep: its % share of the rows that fit in the memory's disk share."""
    avg = int(retention.get("avg_row_bytes", 2048))
    if avg <= 0:
        raise ConfigError("memory.toml retention.avg_row_bytes must be positive")
    total = max(len(STORED_LAYERS), disk_cap_mb * 1024 * 1024 // avg)
    return {layer: max(1, int(total * pct(retention, f"{layer}_pct"))) for layer in STORED_LAYERS}


class MemoryStore:
    """Episodic, semantic, procedural and session memory in the project's SQLite database (its own tables).

    Writes are deduplicated by content; repeats across runs are counted (the evidence for promotion). Retrieval is
    BM25 through SQLite FTS5 when the build has it, otherwise BM25 in Python over a bounded candidate set.
    """

    def __init__(self, conn: sqlite3.Connection, caps: dict[str, int] | None = None, retention: dict[str, Any] | None = None, cache_mb: int | None = None) -> None:
        self.conn = conn
        self.lock = threading.RLock()
        if self.conn.row_factory is None:
            self.conn.row_factory = sqlite3.Row
        self.caps = caps or {layer: 10_000 for layer in STORED_LAYERS}
        self.retention = retention or {"min_score_pct": 15, "promote_after": 2, "retire_harmful_pct": 60}
        if cache_mb:
            self.conn.execute(f"PRAGMA cache_size = -{int(cache_mb) * 1024}")
        self.conn.executescript(_SCHEMA)
        try:
            self.conn.executescript(_FTS)
            self.fts = True
        except sqlite3.OperationalError:
            logger.warning("this SQLite build has no FTS5; memory search uses Python BM25 over recent rows")
            self.fts = False
        self.conn.commit()

    # -- writing ---------------------------------------------------------------------------------------------------------

    @_locked
    def remember(self, record: MemoryRecord) -> int:
        """Store a record, or reinforce the identical one already stored (a new run is added to its evidence)."""
        now = time.time()
        found = self.conn.execute(
            "SELECT id, runs FROM mem_records WHERE layer = ? AND scope = ? AND content_hash = ?", (record.layer, record.scope, record.content_hash)
        ).fetchone()
        if found is not None:
            runs: list[str] = json.loads(found["runs"])
            if record.run_id and record.run_id not in runs:
                runs.append(record.run_id)
            self.conn.execute("UPDATE mem_records SET runs = ?, last_used = ? WHERE id = ?", (json.dumps(runs), now, found["id"]))
            self.conn.commit()
            return int(found["id"])
        cur = self.conn.execute(
            "INSERT INTO mem_records (layer, scope, topic, title, text, tags, content_hash, source_hash, trusted, run_id, task_id, runs, helpful, harmful, created, last_used) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.layer, record.scope, record.topic, record.title, record.text, json.dumps(record.tags), record.content_hash, record.source_hash,
                int(record.trusted), record.run_id, record.task_id, json.dumps([record.run_id] if record.run_id else []), record.helpful, record.harmful, now, now,
            ),
        )
        self.conn.commit()
        self._evict(record.layer)
        return int(cur.lastrowid or 0)

    @_locked
    def _evict(self, layer: str) -> int:
        """Keep the layer inside its row share: drop the least useful rows (harmful, unused, oldest) first."""
        count = int(self.conn.execute("SELECT COUNT(*) FROM mem_records WHERE layer = ?", (layer,)).fetchone()[0])
        excess = count - self.caps.get(layer, count)
        if excess <= 0:
            return 0
        self.conn.execute(
            "DELETE FROM mem_records WHERE id IN (SELECT id FROM mem_records WHERE layer = ? ORDER BY (helpful - harmful) ASC, uses ASC, last_used ASC LIMIT ?)",
            (layer, excess),
        )
        self.conn.commit()
        return excess

    @_locked
    def mark_outcome(self, ids: list[int], helpful: bool) -> list[int]:
        """Record whether the included memory helped (gate passed) or hurt; retire procedural rules that mostly hurt."""
        if not ids:
            return []
        column = "helpful" if helpful else "harmful"
        marks = ",".join("?" * len(ids))
        self.conn.execute(f"UPDATE mem_records SET {column} = {column} + 1 WHERE id IN ({marks})", ids)  # noqa: S608 - column is fixed
        limit = pct(self.retention, "retire_harmful_pct")
        retired = [
            int(r["id"])
            for r in self.conn.execute(
                f"SELECT id, helpful, harmful FROM mem_records WHERE layer = 'procedural' AND id IN ({marks})", ids  # noqa: S608 - placeholders only
            )
            if r["helpful"] + r["harmful"] >= 3 and r["harmful"] / (r["helpful"] + r["harmful"]) >= limit
        ]
        if retired:
            self.conn.execute(f"DELETE FROM mem_records WHERE id IN ({','.join('?' * len(retired))})", retired)  # noqa: S608 - placeholders only
        self.conn.commit()
        return retired

    @_locked
    def touch(self, ids: list[int]) -> None:
        if ids:
            self.conn.execute(f"UPDATE mem_records SET uses = uses + 1, last_used = ? WHERE id IN ({','.join('?' * len(ids))})", [time.time(), *ids])  # noqa: S608
            self.conn.commit()

    @_locked
    def invalidate(self, current_hashes: dict[str, str]) -> int:
        """Delete semantic facts whose source file (their topic) changed or disappeared since they were learned."""
        stale = [
            int(r["id"])
            for r in self.conn.execute("SELECT id, topic, source_hash FROM mem_records WHERE layer = 'semantic' AND source_hash IS NOT NULL")
            if current_hashes.get(r["topic"]) != r["source_hash"]
        ]
        if stale:
            self.conn.execute(f"DELETE FROM mem_records WHERE id IN ({','.join('?' * len(stale))})", stale)  # noqa: S608 - placeholders only
            self.conn.commit()
        return len(stale)

    # -- consolidation ---------------------------------------------------------------------------------------------------

    @_locked
    def end_session(self, run_id: str, outcome: str) -> int | None:
        """Fold a finished run's session notes into one episodic record and drop the session rows."""
        rows = self.conn.execute("SELECT title, text FROM mem_records WHERE layer = 'session' AND scope = ? ORDER BY id", (f"run:{run_id}",)).fetchall()
        if not rows:
            return None
        body = "\n".join(f"- {r['title']}: {r['text'][:300]}" for r in rows)
        rid = self.remember(MemoryRecord(layer="episodic", topic=f"run/{run_id}", title=f"run {run_id}: {outcome}", text=body, tags=["run", outcome.lower()], run_id=run_id))
        self.conn.execute("DELETE FROM mem_records WHERE layer = 'session' AND scope = ?", (f"run:{run_id}",))
        self.conn.commit()
        return rid

    @_locked
    def promote(self) -> list[int]:
        """Episodic lessons seen in ``promote_after`` different runs become procedural playbook rules (ACE-style deltas)."""
        need = int(self.retention.get("promote_after", 2))
        promoted: list[int] = []
        for r in self.conn.execute("SELECT * FROM mem_records WHERE layer = 'episodic' AND tags LIKE '%\"lesson\"%'").fetchall():
            if len(json.loads(r["runs"])) >= need and r["trusted"]:
                promoted.append(
                    self.remember(MemoryRecord(layer="procedural", topic=r["topic"], title=r["title"], text=r["text"], tags=[*json.loads(r["tags"]), "promoted"]))
                )
        return promoted

    # -- reading ---------------------------------------------------------------------------------------------------------

    def _from_row(self, r: sqlite3.Row, score: float = 0.0) -> MemoryRecord:
        return MemoryRecord(
            id=int(r["id"]), layer=r["layer"], scope=r["scope"], topic=r["topic"], title=r["title"], text=r["text"], tags=json.loads(r["tags"]),
            source_hash=r["source_hash"], trusted=bool(r["trusted"]), run_id=r["run_id"], task_id=r["task_id"], helpful=int(r["helpful"]),
            harmful=int(r["harmful"]), runs=json.loads(r["runs"]), score=score,
        )

    @_locked
    def search(self, query: str, layers: list[str], scopes: list[str] | None = None, limit: int = 20) -> list[MemoryRecord]:
        """Best matches first; anything scoring below ``min_score_pct`` of the best match is left out."""
        scopes = scopes or ["project"]
        layer_marks, scope_marks = ",".join("?" * len(layers)), ",".join("?" * len(scopes))
        found: list[MemoryRecord] = []
        match = " OR ".join(f'"{t}"' for t in dict.fromkeys(_fts_terms(query)))
        if self.fts and match:
            rows = self.conn.execute(
                "SELECT r.*, -bm25(mem_fts) AS s FROM mem_fts JOIN mem_records r ON r.id = mem_fts.rowid "  # noqa: S608 - placeholders only
                f"WHERE mem_fts MATCH ? AND r.layer IN ({layer_marks}) AND r.scope IN ({scope_marks}) ORDER BY s DESC LIMIT ?",
                [match, *layers, *scopes, limit],
            ).fetchall()
            found = [self._from_row(r, float(r["s"])) for r in rows]
        elif match:
            rows = self.conn.execute(
                f"SELECT * FROM mem_records WHERE layer IN ({layer_marks}) AND scope IN ({scope_marks}) ORDER BY last_used DESC LIMIT ?",  # noqa: S608
                [*layers, *scopes, max(limit * 20, 200)],
            ).fetchall()
            scores = Bm25(f"{r['title']} {r['text']} {r['tags']} {r['topic']}" for r in rows).scores(query)
            found = sorted((self._from_row(r, s) for r, s in zip(rows, scores, strict=True) if s > 0), key=lambda m: -m.score)[:limit]
        if not found:
            return []
        floor = found[0].score * pct(self.retention, "min_score_pct")
        return [m for m in found if m.score >= floor]

    def iter_records(self, layers: list[str], scopes: list[str] | None = None) -> Iterator[MemoryRecord]:
        """Every record of the layers, streamed from the cursor (the tree index is built from this)."""
        scopes = scopes or ["project"]
        with self.lock:
            rows = self._records(layers, scopes)
        yield from rows

    def _records(self, layers: list[str], scopes: list[str]) -> list[MemoryRecord]:
        cur = self.conn.execute(
            f"SELECT * FROM mem_records WHERE layer IN ({','.join('?' * len(layers))}) AND scope IN ({','.join('?' * len(scopes))}) ORDER BY topic, id",  # noqa: S608
            [*layers, *scopes],
        )
        return [self._from_row(row) for row in cur]

    @_locked
    def version(self) -> tuple[int, int, float]:
        row = self.conn.execute("SELECT COUNT(*), COALESCE(MAX(id), 0), COALESCE(MAX(last_used), 0) FROM mem_records").fetchone()
        return int(row[0]), int(row[1]), float(row[2])

    @_locked
    def stats(self) -> dict[str, int]:
        counts: dict[str, int] = {layer: 0 for layer in STORED_LAYERS}
        for r in self.conn.execute("SELECT layer, COUNT(*) AS n FROM mem_records GROUP BY layer"):
            counts[str(r["layer"])] = int(r["n"])
        return counts


def open_memory_store(path: Path, caps: dict[str, int] | None = None, retention: dict[str, Any] | None = None, cache_mb: int | None = None) -> MemoryStore:
    """The project's memory database (``.factory/memory.db``), shared safely by the main and scheduler threads."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return MemoryStore(conn, caps=caps, retention=retention, cache_mb=cache_mb)


def _fts_terms(query: str) -> list[str]:
    return [t.replace('"', "") for t in terms(query)][:32]
