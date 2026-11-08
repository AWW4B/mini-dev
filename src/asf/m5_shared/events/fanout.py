# FILE: src/asf/m5_shared/events/fanout.py
# ROLE: Delivers new events to in-process subscribers (scheduler, decomposition, CLI follow mode) in seq order.
# ARCH REF: M5; p10 fan-out; IF-18 EventSubscribe
# OWNS: Subscriber registry and polling iterator
# DOES NOT OWN: Persisting events
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/events/event_log.py: EventLog (source of events)
#   - imports from src/asf/contracts/events.py: EventEnvelope, EventKind (shape)
#   - called by src/asf/cli/views/trace_view.py: EventFanout
#   - called by tests/m5_shared/events/test_fanout.py: EventFanout
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Subscribers resume from a cursor (last seq); a disconnected subscriber loses nothing.
#   6. Polling interval comes from settings; never busy-wait.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/events/test_fanout.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/events/fanout.py` and `uv run mypy src/asf/m5_shared/events/fanout.py` are clean.

from collections.abc import Iterator

from asf.contracts.events import EventEnvelope, EventKind
from asf.m5_shared.events.event_log import EventLog


class EventFanout:
    def __init__(self, log: EventLog) -> None:
        raise NotImplementedError

    def follow(self, run_id: str, after_seq: int, kinds: set[EventKind] | None = None) -> Iterator[EventEnvelope]:
        """Yield events after the cursor, blocking politely until cancelled."""
        raise NotImplementedError
