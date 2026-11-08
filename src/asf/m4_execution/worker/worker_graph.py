# FILE: src/asf/m4_execution/worker/worker_graph.py
# ROLE: One attempt of the Local Coding Worker: worktree, ContextPack, bounded loop, ChangeSet to the gate. No checkpointer (D-05).
# ARCH REF: M4; p07 Local Coding Worker; IF-11; IF-12; IF-14; IF-15; IF-21 ChangeSet; D-05
# OWNS: Attempt lifecycle
# DOES NOT OWN: Pass/fail decisions (gate)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tasks.py: LeafTaskSpec (IF-09)
#   - imports from src/asf/contracts/outcomes.py: ChangeSet (IF-21)
#   - imports from src/asf/contracts/models.py: SlotLease (IF-13)
#   - imports from src/asf/m4_execution/worker/strategies.py: run_strategy (loop)
#   - imports from src/asf/m4_execution/verification/gate.py: verify_change_set (IF-21)
#   - imports from src/asf/m5_shared/workspace/workspace.py: Workspace (IF-15 git operations)
#   - imports from src/asf/m5_shared/context/context_service.py: ContextService (IF-11 ContextPack)
#   - called by src/asf/m4_execution/scheduler.py: run_attempt
#   - called by tests/m4_execution/worker/test_worker_graph.py: run_attempt
#   - emits/consumes: emits TASK_RECEIVED, STEP_STARTED, HANDOFF_SENT (worker -> gate); tool events come from ToolExecutor
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Never resume an interrupted attempt; recovery resets the worktree and the scheduler re-dispatches (D-06).
#   9. Heartbeat the lease while running.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m4_execution/worker/test_worker_graph.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m4_execution/worker/worker_graph.py` and `uv run mypy src/asf/m4_execution/worker/worker_graph.py` are clean.

from asf.contracts.models import SlotLease
from asf.contracts.outcomes import ChangeSet
from asf.contracts.tasks import LeafTaskSpec


def run_attempt(spec: LeafTaskSpec, lease: SlotLease, attempt_no: int) -> ChangeSet:
    raise NotImplementedError
