# FILE: src/asf/m5_shared/events/event_log.py
# ROLE: Appends EventEnvelopes to the events table and reads them back by run and seq cursor.
# ARCH REF: M5; p10 Event Stream; IF-17 EventPublish; IF-18 EventSubscribe; D-23; D-14b
# OWNS: The events table contents, seq assignment, blob offload for payloads over 8 KB
# DOES NOT OWN: Fan-out to live subscribers (fanout.py); rendering (cli views, web)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/events.py: EventEnvelope, Visibility (IF-17 shape)
#   - imports from src/asf/m5_shared/events/redaction.py: redact_payload (redaction)
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (large payloads)
#   - called by src/asf/m5_shared/state_store/outbox.py: EventLog
#   - called by src/asf/m5_shared/events/fanout.py: EventLog
#   - called by src/asf/cli/commands/events.py: EventLog
#   - called by src/asf/web/projection.py: EventLog
#   - called by tests/m5_shared/events/test_event_log.py: EventLog
#   - emits/consumes: stores EventEnvelope (all EventKind values incl. narrative kinds); serves them ordered by seq
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. seq is monotonic per run and assigned inside the append transaction; append is idempotent on event_id.
#   9. Always redact payloads before storing.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/events/test_event_log.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/events/event_log.py` and `uv run mypy src/asf/m5_shared/events/event_log.py` are clean.

from collections.abc import Sequence

from asf.contracts.events import EventEnvelope, Visibility


class EventLog:
    def append(self, events: Sequence[EventEnvelope]) -> list[int]:
        """Store events (idempotent on event_id); return assigned seq numbers."""
        raise NotImplementedError

    def read(self, run_id: str, after_seq: int = 0, limit: int = 500, visibility: Visibility | None = None) -> list[EventEnvelope]:
        raise NotImplementedError

    def latest_seq(self, run_id: str) -> int:
        raise NotImplementedError
