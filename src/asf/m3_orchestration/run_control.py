# FILE: src/asf/m3_orchestration/run_control.py
# ROLE: Foreground supervisor loop: polls the command table, applies pause/resume/abort/cancel-task and broadcasts CancelSignal.
# ARCH REF: M3; p04 Run Control; IF-05 RunControl; IF-06 CancelSignal; D-15
# OWNS: Command handling and Ctrl+C clean pause
# DOES NOT OWN: Writing commands (CLI)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/control.py: RunControl, RunCommand, CancelSignal (IF-05/IF-06)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (IF-16 state)
#   - imports from src/asf/platform/select.py: get_platform (platform adapter)
#   - imports from src/asf/m4_execution/scheduler.py: TaskScheduler (receives CancelSignal)
#   - imports from src/asf/m5_shared/runtime/local_runtime.py: LocalRuntime (lease revocation)
#   - imports from src/asf/contracts/state.py: StateCommit (run status plus CANCELLED / STATE_CHANGED events)
#   - called by tests/m3_orchestration/test_run_control.py: RunSupervisor
#   - called by src/asf/m3_orchestration/run_graph.py: RunSupervisor
#   - emits/consumes: emits CANCELLED and STATE_CHANGED events
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Validate command_id idempotently; install the Ctrl+C handler via the platform adapter so an interrupt becomes a clean PAUSE.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/test_run_control.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/run_control.py` and `uv run mypy src/asf/m3_orchestration/run_control.py` are clean.

import logging
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from asf.contracts.control import CancelSignal, RunCommand, RunControl
from asf.contracts.state import StateCommit
from asf.m4_execution.scheduler import TaskScheduler
from asf.m5_shared.runtime.local_runtime import LocalRuntime
from asf.m5_shared.state_store.store import StateStore
from asf.platform.select import get_platform

logger = logging.getLogger(__name__)

_TERMINAL = ("DONE", "ABORTED", "CANCELLED", "FAILED")
_STATUS_AFTER = {
    RunCommand.PAUSE: "PAUSED",
    RunCommand.RESUME: "RUNNING",
    RunCommand.ABORT: "CANCELLED",
    RunCommand.CANCEL_TASK: None,  # a task command does not change the run's own status
}


class RunSupervisor:
    """Foreground supervisor: applies pause / resume / abort / cancel-task and broadcasts the CancelSignal (IF-05 -> IF-06)."""

    def __init__(
        self,
        run_id: str,
        *,
        store: StateStore | None = None,
        scheduler: TaskScheduler | None = None,
        runtime: LocalRuntime | None = None,
        reconcile: Callable[[], None] | None = None,
        poll_interval_s: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
        platform: Any = None,
    ) -> None:
        self.run_id = run_id
        self._store = store
        self._scheduler = scheduler
        self._runtime = runtime
        self._reconcile = reconcile
        self._poll_interval_s = poll_interval_s
        self._sleep = sleep
        self._platform = platform
        self._applied: set[str] = set()
        self._queue: deque[RunControl] = deque()
        self._lock = threading.Lock()
        self.status = "RUNNING"
        self.signals: list[CancelSignal] = []

    # -- applying commands ----------------------------------------------------------------------------------------

    def apply(self, command: RunControl) -> CancelSignal | None:
        """Apply one command once. Returns the broadcast CancelSignal, or None when the command was ignored.

        A command is ignored when it is for another run, repeats an already applied command_id, or cannot be carried out
        (resume of a run that is not paused, cancel_task without a task).
        """
        command_id = str(command.command_id)
        if str(command.run_id) != self.run_id:
            logger.warning("ignoring command %s: it is for run %s, this supervisor runs %s", command_id, command.run_id, self.run_id)
            return None
        if command_id in self._applied:
            return None
        verb = command.command
        if verb is RunCommand.CANCEL_TASK and not command.task_id:
            logger.warning("ignoring cancel_task %s: no task_id", command_id)
            return None
        if verb is RunCommand.RESUME and self.status != "PAUSED":
            logger.info("ignoring resume %s: the run is %s, not paused", command_id, self.status)
            return None
        if self.status in _TERMINAL:
            logger.info("ignoring %s %s: the run is already %s", verb.value, command_id, self.status)
            return None
        self._applied.add(command_id)

        if verb is RunCommand.RESUME and self._reconcile is not None:
            self._reconcile()  # recovery runs before anything is dispatched again

        signal = CancelSignal.model_validate(
            {
                "run_id": self.run_id,
                "scope": "task" if verb is RunCommand.CANCEL_TASK else "run",
                "command": verb,
                "task_id": command.task_id if verb is RunCommand.CANCEL_TASK else None,
            }
        )
        new_status = _STATUS_AFTER[verb]
        if new_status is not None:
            self.status = new_status
        self._record(signal, new_status)
        if self._scheduler is not None:
            self._scheduler.on_cancel(signal)  # revokes the leases in scope through the runtime
        if verb is RunCommand.ABORT and self._runtime is not None:
            self._runtime.drop_stale()
        self.signals.append(signal)
        return signal

    def _record(self, signal: CancelSignal, new_status: str | None) -> None:
        """Commit the run's new status with its CANCELLED / STATE_CHANGED event in one transaction."""
        if self._store is None:
            return
        row = self._store.conn.execute("SELECT version FROM runs WHERE run_id = ?", (self.run_id,)).fetchone()
        if row is None:
            logger.warning("run %s has no row in the state store; the command was applied but not recorded", self.run_id)
            return
        kind = "cancelled" if signal.command in (RunCommand.ABORT, RunCommand.CANCEL_TASK) else "state_changed"
        event = {
            "event_id": f"evt-{uuid.uuid4().hex}",
            "run_id": self.run_id,
            "task_id": signal.task_id,
            "seq": 0,
            "ts": datetime.now(UTC).isoformat(),
            "actor": {"kind": "service", "role": "supervisor", "name": "Run supervisor"},
            "kind": kind,
            "correlation_id": self.run_id,
            "payload": {"command": signal.command.value, "scope": signal.scope, "status": new_status},
        }
        self._store.commit(
            StateCommit.model_validate(
                {
                    "entity": "run",
                    "entity_id": self.run_id,
                    "expected_version": int(row["version"]),
                    "mutation": {"status": new_status} if new_status is not None else {},
                    "events": [event],
                }
            )
        )

    # -- the loop -------------------------------------------------------------------------------------------------

    def _on_interrupt(self) -> None:
        """Ctrl+C becomes a clean PAUSE instead of killing the process mid-write."""
        with self._lock:
            self._queue.append(
                RunControl.model_validate({"command_id": f"interrupt-{uuid.uuid4().hex[:12]}", "run_id": self.run_id, "command": "pause"})
            )

    def _run_status(self) -> str | None:
        if self._store is None:
            return None
        row = self._store.conn.execute("SELECT status FROM runs WHERE run_id = ?", (self.run_id,)).fetchone()
        return str(row["status"]) if row is not None else None

    def poll_once(self) -> int:
        """Apply the queued interrupts and every unconsumed command of this run; return how many were applied."""
        with self._lock:
            pending = list(self._queue)
            self._queue.clear()
        if self._store is not None:
            pending += self._store.poll_commands(self.run_id)
        return sum(1 for command in pending if self.apply(command) is not None)

    def loop(self) -> None:
        """Poll commands and advisories until the run is terminal or paused."""
        platform = self._platform if self._platform is not None else get_platform()
        platform.install_interrupt_handler(self._on_interrupt)
        while True:
            self.poll_once()
            stored = self._run_status()
            if stored in _TERMINAL:
                self.status = stored
            if self.status in _TERMINAL or self.status == "PAUSED":
                return
            self._sleep(self._poll_interval_s)

