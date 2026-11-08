# FILE: src/asf/m5_shared/state_store/outbox.py
# ROLE: Relays committed outbox rows to the Event Stream exactly in commit order (at-least-once).
# ARCH REF: M5; p09 outbox; IF-17
# OWNS: Moving outbox rows to the event log
# DOES NOT OWN: Creating events (callers put them in StateCommit.events)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (reads outbox)
#   - imports from src/asf/m5_shared/events/event_log.py: EventLog (IF-17 append)
#   - called by tests/m5_shared/state_store/test_outbox.py: OutboxRelay
#   - emits/consumes: consumes outbox rows; emits EventEnvelope via EventLog.append
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Mark a row relayed only after EventLog.append returns; duplicates are allowed because consumers dedupe by event_id.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/state_store/test_outbox.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/state_store/outbox.py` and `uv run mypy src/asf/m5_shared/state_store/outbox.py` are clean.

import json
from types import SimpleNamespace
from typing import Any

from asf.m5_shared.events.event_log import EventLog
from asf.m5_shared.state_store.store import StateStore


class OutboxRelay:
    store: StateStore
    log: EventLog

    def __init__(self, store: StateStore, log: EventLog) -> None:
        self.store = store
        self.log = log

    def relay_once(self, max_rows: int = 500) -> int:
        """Relay pending outbox rows; return how many were relayed."""
        cur = self.store.conn.execute(
            "SELECT id, payload FROM outbox WHERE published = 0 ORDER BY id ASC LIMIT ?",
            (max_rows,),
        )
        rows = cur.fetchall()
        if not rows:
            return 0

        events: list[Any] = []
        row_ids: list[int] = []
        for row in rows:
            row_ids.append(int(row["id"]))
            raw = row["payload"]
            evt_obj = json.loads(raw, object_hook=lambda d: SimpleNamespace(**d))
            events.append(evt_obj)

        self.log.append(events)

        with self.store.conn:
            placeholders = ",".join("?" for _ in row_ids)
            self.store.conn.execute(
                f"UPDATE outbox SET published = 1 WHERE id IN ({placeholders})",  # noqa: S608
                row_ids,
            )

        return len(rows)
