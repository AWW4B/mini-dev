# FILE: src/asf/cli/views/trace_view.py
# ROLE: Terminal projection of the event log: ordered by seq, replays gaps from the last cursor, collapses internal events by --level.
# ARCH REF: M1; p02 Active Group Chat; IF-18; D-14
# OWNS: Rendering this view
# DOES NOT OWN: Data production
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/events/fanout.py: EventFanout (IF-18)
#   - imports from src/asf/contracts/events.py: EventEnvelope, Visibility (events)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: open_store, resolve_run_id (the project's store and the default run)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (read-only queries)
#   - imports from src/asf/m5_shared/events/event_log.py: EventLog (reading events after a cursor)
#   - called by src/asf/cli/commands/trace.py: TraceView
#   - called by tests/cli/views/test_trace_view.py: TraceView
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Escape all agent/tool text before rendering; never execute or interpret it.
#   6. Refresh using cursors, not busy loops.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/cli/views/test_trace_view.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/views/trace_view.py` and `uv run mypy src/asf/cli/views/trace_view.py` are clean.

import json
import time
from collections.abc import Callable
from typing import Any

from asf.cli.context import open_store, resolve_run_id
from asf.contracts.events import EventEnvelope, Visibility
from asf.m5_shared.events.event_log import EventLog
from asf.m5_shared.events.fanout import EventFanout
from asf.m5_shared.state_store.store import StateStore


def _summary(event: EventEnvelope) -> str:
    text = json.dumps(event.payload, ensure_ascii=False, default=str) if event.payload else ""
    return text if len(text) <= 120 else text[:117] + "..."


class TraceView:
    """Terminal projection of the event log: ordered by seq, resumed from the last cursor, internal events hidden by --level user."""

    def __init__(
        self,
        renderer: Any,
        run_id: str | None,
        *,
        level: str = "user",
        task: str | None = None,
        store: StateStore | None = None,
        interval_s: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if level not in ("user", "internal"):
            raise ValueError("level must be 'user' or 'internal'")
        self.renderer = renderer
        self.run_id = run_id
        self.level = level
        self.task = task
        self.cursor = 0
        self._store = store
        self._interval_s = interval_s
        self._sleep = sleep
        self._fanout: EventFanout | None = None

    def _log(self) -> tuple[EventLog, str]:
        store = self._store if self._store is not None else open_store(readonly=True)
        return EventLog(store.conn), resolve_run_id(store, self.run_id)

    def _wanted(self, event: EventEnvelope) -> bool:
        if self.level == "user" and event.visibility is not Visibility.USER:
            return False
        return self.task is None or str(event.task_id) == self.task

    def _row(self, event: EventEnvelope) -> list[Any]:
        return [event.seq, event.ts.strftime("%H:%M:%S"), event.actor.name, event.kind.value, str(event.task_id or "-"), _summary(event)]

    def render_once(self) -> int:
        """Print every wanted event after the cursor, advance the cursor and return it. Calling again prints only new events."""
        log, run_id = self._log()
        rows: list[list[Any]] = []
        while True:
            batch = log.read(run_id, after_seq=self.cursor, limit=500)
            if not batch:
                break
            for event in batch:
                self.cursor = max(self.cursor, event.seq)
                if self._wanted(event):
                    rows.append(self._row(event))
        if rows:
            self.renderer.table(f"Trace of run {run_id}", ["seq", "time", "who", "event", "task", "details"], rows)
        return self.cursor

    def live(self) -> None:
        """Follow the run until Ctrl+C (which only exits the view)."""
        log, run_id = self._log()
        self._fanout = EventFanout(log, poll_interval=self._interval_s)
        try:
            for event in self._fanout.follow(run_id, self.cursor):
                self.cursor = max(self.cursor, event.seq)
                if self._wanted(event):
                    self.renderer.table(f"Trace of run {run_id}", ["seq", "time", "who", "event", "task", "details"], [self._row(event)])
        except KeyboardInterrupt:
            self._fanout.stop()
            self.renderer.message("view closed (the run keeps going)")
