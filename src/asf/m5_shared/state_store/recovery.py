# FILE: src/asf/m5_shared/state_store/recovery.py
# ROLE: Reconciles state after a crash or restart before any graph resumes (SEQ-2).
# ARCH REF: M5; p09 recovery; p14 SEQ-2; D-06; p16 interruption row
# OWNS: Startup reconciliation steps and the RecoveryReport
# DOES NOT OWN: Resuming LangGraph threads (run_graph does that after reconciliation)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (state)
#   - imports from src/asf/m5_shared/workspace/workspace.py: Workspace (IF-15 reset worktrees)
#   - imports from src/asf/m5_shared/runtime/local_runtime.py: LocalRuntime (drop stale slots)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (re-arm decisions)
#   - called by tests/m5_shared/state_store/test_recovery.py: RecoveryReport, reconcile_on_startup
#   - emits/consumes: emits RUN_RECOVERED and STATE_CHANGED events through StateStore.commit
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Order: expire leases (RUNNING -> READY, interruptions+1, >3 -> ESCALATED), reset interrupted worktrees to base commit, re-probe runtime, re-arm decisions, restore frontier, then report.
#   9. Never re-run or modify VERIFIED or INTEGRATED tasks.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/state_store/test_recovery.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/state_store/recovery.py` and `uv run mypy src/asf/m5_shared/state_store/recovery.py` are clean.

from pydantic import BaseModel

from asf.m5_shared.decisions.broker import DecisionBroker
from asf.m5_shared.runtime.local_runtime import LocalRuntime
from asf.m5_shared.state_store.store import StateStore
from asf.m5_shared.workspace.workspace import Workspace


class RecoveryReport(BaseModel):
    runs_checked: int
    tasks_reset: list[str]
    tasks_escalated: list[str]
    decisions_rearmed: int


def reconcile_on_startup(store: StateStore, workspace: Workspace, runtime: LocalRuntime, broker: DecisionBroker) -> RecoveryReport:
    raise NotImplementedError
