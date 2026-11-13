# FILE: src/asf/web/projection.py
# ROLE: Projects events into the viewer model: participants (role, colour, avatar, model tier, task, short result) and expandable details.
# ARCH REF: M1; p02 Active Group Chat; IF-18; D-14b
# OWNS: View-model projection and detail lookup (diff, test log, ContextPack manifest)
# DOES NOT OWN: Narrative text (narrative.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/events/event_log.py: EventLog (read-only reads)
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (details)
#   - imports from src/asf/web/narrative.py: build_narrative, NarrativeItem (narrative)
#   - imports from src/asf/contracts/events.py: EventEnvelope, Visibility (the events being projected)
#   - imports from src/asf/m5_shared/events/redaction.py: redact_text (details are redacted)
#   - called by src/asf/web/server.py: Projection
#   - called by tests/web/test_projection.py: Participant, Projection
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Open state.db read-only (SQLite URI mode=ro).
#   6. Participant colour/avatar are deterministic from the role name.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/web/test_projection.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/web/projection.py` and `uv run mypy src/asf/web/projection.py` are clean.

import hashlib
import re
import sqlite3
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from asf.contracts.events import EventEnvelope, Visibility
from asf.m5_shared.events.event_log import EventLog
from asf.m5_shared.events.redaction import redact_text
from asf.m5_shared.workspace.blobs import BlobStore
from asf.web.narrative import NarrativeItem, build_narrative, derive_handoffs

MAX_DETAIL_BYTES = 200_000
_PALETTE = ("#2563eb", "#16a34a", "#d97706", "#9333ea", "#dc2626", "#0891b2", "#be185d", "#65a30d")
_REF = re.compile(r"sha256:[0-9a-f]{64}")


class Participant(BaseModel):
    key: str
    role: str
    colour: str
    avatar: str
    model_tier: str | None
    current_task: str | None
    last_result: str | None


def _colour(role: str) -> str:
    """Deterministic from the role name (not from hash(), which changes between runs)."""
    return _PALETTE[int(hashlib.sha256(role.encode("utf-8")).hexdigest(), 16) % len(_PALETTE)]


def _avatar(role: str) -> str:
    letters = re.findall(r"[A-Za-z0-9]", role)
    return "".join(letters[:2]).upper() or "?"


class Projection:
    """Read-only view model over one run's events: participants, a narrative page and expandable details."""

    def __init__(
        self,
        run_id: str | None,
        *,
        db_path: Path | None = None,
        conn: sqlite3.Connection | None = None,
        blobs: BlobStore | None = None,
    ) -> None:
        if conn is None:
            path = db_path or Path.cwd() / ".factory" / "state.db"
            if not path.is_file():
                raise FileNotFoundError(f"No state database at {path}. Run `factory init` in the project directory first.")
            conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)  # read-only: the viewer can never write
            conn.row_factory = sqlite3.Row
            self._owns_conn = True
        else:
            self._owns_conn = False
        self._conn = conn
        self._log = EventLog(conn)
        self._blobs = blobs
        self.run_id = run_id or self._latest_run()

    def close(self) -> None:
        if self._owns_conn:
            self._conn.close()

    def _latest_run(self) -> str:
        row = self._conn.execute("SELECT run_id FROM runs ORDER BY last_activity DESC, rowid DESC LIMIT 1").fetchone()
        if row is None:
            raise LookupError("This project has no runs yet.")
        return str(row["run_id"])

    def _events(self, after_seq: int, limit: int) -> list[EventEnvelope]:
        return self._log.read(self.run_id, after_seq=after_seq, limit=limit)

    def _all_events(self) -> list[EventEnvelope]:
        events: list[EventEnvelope] = []
        cursor = 0
        while True:
            batch = self._events(cursor, 500)
            if not batch:
                return events
            events += batch
            cursor = batch[-1].seq

    def participants(self) -> list[Participant]:
        """Everyone who acted in the run (user-visible events), in order of first appearance."""
        by_key: dict[str, Participant] = {}
        for event in self._all_events():
            if event.visibility is not Visibility.USER:
                continue
            name = redact_text(event.actor.name)
            current = by_key.get(name)
            tier = event.actor.model_tier or (current.model_tier if current else None)
            result = current.last_result if current else None
            for item in build_narrative([event]):
                if item.kind in ("gate_result", "tool_result"):
                    result = item.summary
            by_key[name] = Participant(
                key=name,
                role=event.actor.role,
                colour=_colour(event.actor.role),
                avatar=_avatar(event.actor.role),
                model_tier=tier,
                current_task=str(event.task_id) if event.task_id is not None else (current.current_task if current else None),
                last_result=result,
            )
        return list(by_key.values())

    def page(self, after_seq: int, limit: int = 200, include_internal: bool = False) -> dict[str, Any]:
        """Narrative items after the cursor. ``next_seq`` also advances over events that were filtered out."""
        limit = max(1, min(limit, 1000))
        events = self._events(after_seq, limit)
        visible = [e for e in events if include_internal or e.visibility is Visibility.USER]
        items: list[NarrativeItem] = build_narrative(visible)
        status_row = self._conn.execute("SELECT status FROM runs WHERE run_id = ?", (self.run_id,)).fetchone()
        return {
            "run_id": self.run_id,
            "status": str(status_row["status"]) if status_row is not None else "UNKNOWN",
            "items": [item.model_dump() for item in items],
            "handoffs": [h.model_dump() for h in derive_handoffs(visible)],
            "participants": [p.model_dump() for p in self.participants()],
            "next_seq": events[-1].seq if events else after_seq,
            "more": len(events) == limit,
        }

    def detail(self, ref: str) -> dict[str, Any]:
        """The text behind a detail link (a diff, a test log, a ContextPack manifest): a blob, redacted and size-capped."""
        if _REF.fullmatch(ref) is None:
            return {"ref": ref, "error": "not a detail reference"}
        blobs = self._blobs if self._blobs is not None else BlobStore()
        try:
            data = blobs.get(ref)
        except FileNotFoundError:
            return {"ref": ref, "error": "the detail is no longer available"}
        truncated = len(data) > MAX_DETAIL_BYTES
        text = data[:MAX_DETAIL_BYTES].decode("utf-8", errors="replace")
        return {"ref": ref, "text": redact_text(text), "truncated": truncated, "bytes": len(data)}
