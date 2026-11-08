# FILE: src/asf/m3_orchestration/run_graph.py
# ROLE: Main Orchestrator: the durable run graph from StructuredRequest to final acceptance and report.
# ARCH REF: M3; p01 HLD; p04 Main Orchestrator; p13 SEQ-1 happy path; p14 SEQ-2 recovery; IF-02; IF-10b; IF-10c; D-04; D-05; D-06
# OWNS: Run lifecycle, budgets, mode selection, re-plan loop, final acceptance
# DOES NOT OWN: Decomposition (decomposition_graph); execution (M4)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/requests.py: StructuredRequest (IF-02)
#   - imports from src/asf/contracts/outcomes.py: DecompositionReport, RootIntegrated (IF-10b/IF-10c)
#   - imports from src/asf/contracts/budget.py: RunBudget (budgets)
#   - imports from src/asf/m3_orchestration/planning/planner_graph.py: build_planner_graph (planning)
#   - imports from src/asf/m3_orchestration/decomposition/decomposition_graph.py: build_decomposition_graph (decomposition)
#   - imports from src/asf/m3_orchestration/acceptance.py: final_acceptance (final gate)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (IF-16 state)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (IF-03 decisions)
#   - called by src/asf/cli/commands/run.py: start_run, resume_run
#   - called by tests/m3_orchestration/test_run_graph.py: build_run_graph, start_run, resume_run
#   - emits/consumes: emits RUN_STARTED, RUN_COMPLETED, emits narrative events TASK_RECEIVED, STEP_STARTED, HANDOFF_SENT, HANDOFF_RECEIVED (with causation_id set to the triggering event) via StateStore.commit
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Build the graph with LangGraph StateGraph; side-effecting steps use the Functional API @task so they are not re-run on resume (D-04).
#   6. Nodes must be idempotent up to any interrupt(): write the DecisionRequest through DecisionBroker first, then call interrupt() (D-06).
#   7. Pass thread_id = the run or node id; use the SqliteSaver from checkpoints.db with durability="sync" (D-05).
#   8. Re-plan uncovered requirements at most 2 rounds, then HITL.
#   9. Never deploy; deliver a report only.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/test_run_graph.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/run_graph.py` and `uv run mypy src/asf/m3_orchestration/run_graph.py` are clean.

from pathlib import Path
from typing import Any

from asf.contracts.requests import StructuredRequest


def build_run_graph(checkpointer: Any) -> Any:
    raise NotImplementedError


def start_run(request: StructuredRequest, project_root: Path, overrides: dict[str, Any]) -> str:
    """Create the run (budgets, mode) and drive the run graph in the foreground supervisor; return run_id."""
    raise NotImplementedError


def resume_run(run_id: str, project_root: Path) -> None:
    """Reconcile (state_store.recovery) then resume the graph by thread_id."""
    raise NotImplementedError
