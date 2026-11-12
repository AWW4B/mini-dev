# FILE: src/asf/m5_shared/state_store/outbox.py
# ROLE: Relays committed outbox rows to the Event Stream exactly in commit order (at-least-once).
# ARCH REF: M5; p09 outbox; IF-17
# OWNS: Moving outbox rows to the event log
# DOES NOT OWN: Creating events (callers put them in StateCommit.events)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (reads outbox)
#   - imports from src/asf/m5_shared/events/event_log.py: EventLog (IF-17 append)
#   - imports from src/asf/contracts/events.py: EventEnvelope (the parsed outbox payload)
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

import logging

from pydantic import ValidationError

from asf.contracts.events import EventEnvelope
from asf.m5_shared.events.event_log import EventLog
from asf.m5_shared.state_store.store import StateStore

logger = logging.getLogger(__name__)

_PUBLISHED = 1
_QUARANTINED = -1  # unparseable payload: kept for inspection, never retried


class OutboxRelay:
    store: StateStore
    log: EventLog

    def __init__(self, store: StateStore, log: EventLog) -> None:
        self.store = store
        self.log = log

    def relay_once(self, max_rows: int = 500) -> int:
        """Relay pending outbox rows in commit order; return how many were relayed.

        A row whose payload is not a valid EventEnvelope is quarantined (logged and marked, not retried) so that
        one bad row can never block every event behind it.
        """
        rows = self.store.conn.execute(
            "SELECT id, payload FROM outbox WHERE published = 0 ORDER BY id ASC LIMIT ?",
            (max_rows,),
        ).fetchall()
        if not rows:
            return 0

        events: list[EventEnvelope] = []
        relayed_ids: list[int] = []
        quarantined_ids: list[int] = []
        for row in rows:
            row_id = int(row["id"])
            try:
                events.append(EventEnvelope.model_validate_json(row["payload"]))
            except ValidationError:
                logger.error("outbox row %d is not a valid EventEnvelope; quarantined", row_id, exc_info=True)
                quarantined_ids.append(row_id)
            else:
                relayed_ids.append(row_id)

        if events:
            self.log.append(events)

        with self.store.conn:
            self.store.conn.executemany(
                "UPDATE outbox SET published = ? WHERE id = ?",
                [(_PUBLISHED, i) for i in relayed_ids] + [(_QUARANTINED, i) for i in quarantined_ids],
            )

        return len(relayed_ids)
