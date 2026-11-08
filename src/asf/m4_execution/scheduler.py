# FILE: src/asf/m4_execution/scheduler.py
# ROLE: Task Scheduler: dependency-, resource- and model-aware dispatch with slot leases; plain Python, no LangGraph.
# ARCH REF: M4; p07 Task Scheduler; IF-09; IF-10; IF-13; IF-06; IF-20; IF-21 Requeue; D-06
# OWNS: Ready set, ranking, lease acquisition, dispatch, requeue
# DOES NOT OWN: Running attempts (worker_graph)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tasks.py: LeafTaskSpec (IF-09)
#   - imports from src/asf/contracts/outcomes.py: Requeue, TaskOutcome (IF-21/IF-10)
#   - imports from src/asf/contracts/control.py: CancelSignal (IF-06)
#   - imports from src/asf/contracts/metrics.py: ResourceAdvisory (IF-20)
#   - imports from src/asf/m5_shared/runtime/local_runtime.py: LocalRuntime (IF-13)
#   - imports from src/asf/m4_execution/worker/worker_graph.py: run_attempt (dispatch)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (IF-16 state)
#   - called by src/asf/m3_orchestration/run_control.py: TaskScheduler
#   - called by src/asf/m3_orchestration/decomposition/decomposition_graph.py: TaskScheduler
#   - called by src/asf/m4_execution/integration/integrator.py: TaskScheduler
#   - called by tests/m4_execution/test_scheduler.py: TaskScheduler
#   - emits/consumes: emits STATE_CHANGED and HANDOFF_SENT (scheduler -> worker, causation = the READY event)
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Upsert by idempotency key; hold BLOCKED until deps VERIFIED; wait for SLOT_FREE without busy polling.
#   6. Dispatch cap = max_slots from the runtime.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m4_execution/test_scheduler.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m4_execution/scheduler.py` and `uv run mypy src/asf/m4_execution/scheduler.py` are clean.

from asf.contracts.control import CancelSignal
from asf.contracts.metrics import ResourceAdvisory
from asf.contracts.outcomes import Requeue
from asf.contracts.tasks import LeafTaskSpec


class TaskScheduler:
    def enqueue(self, spec: LeafTaskSpec) -> None:
        """IF-09."""
        raise NotImplementedError

    def requeue(self, item: Requeue) -> None:
        """IF-21: READY again if attempts < max_attempts, else TaskOutcome ESCALATED (IF-10)."""
        raise NotImplementedError

    def on_cancel(self, signal: CancelSignal) -> None:
        raise NotImplementedError

    def on_advisory(self, advisory: ResourceAdvisory) -> None:
        raise NotImplementedError

    def dispatch_ready(self) -> int:
        raise NotImplementedError
