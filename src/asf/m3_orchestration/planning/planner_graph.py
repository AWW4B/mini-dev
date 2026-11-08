# FILE: src/asf/m3_orchestration/planning/planner_graph.py
# ROLE: Planning Agent graph: plan the module tree, declare contracts top-down (A-1), add shared-type leaves (A-2), and get approval.
# ARCH REF: M3; p04 Planning Agent; IF-07; IF-07a ApprovedPlan; A-1; A-2
# OWNS: Plan production and approval
# DOES NOT OWN: Decomposing below module level
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/outcomes.py: ApprovedPlan (IF-07a)
#   - imports from src/asf/m3_orchestration/planning/modes.py: select_mode (mode)
#   - imports from src/asf/m3_orchestration/planning/strategies.py: run_planner_strategy (strategy)
#   - imports from src/asf/m5_shared/registry/registry.py: ContractRegistry (IF-07/IF-08)
#   - imports from src/asf/m5_shared/context/context_service.py: ContextService (IF-11 ContextPack)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (IF-03 decisions)
#   - called by src/asf/m3_orchestration/run_graph.py: build_planner_graph
#   - called by tests/m3_orchestration/planning/test_planner_graph.py: build_planner_graph
#   - emits/consumes: raises DecisionRequest kind APPROVE_PLAN; emits narrative events TASK_RECEIVED, STEP_STARTED, HANDOFF_SENT, HANDOFF_RECEIVED (with causation_id set to the triggering event) via StateStore.commit
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Build the graph with LangGraph StateGraph; side-effecting steps use the Functional API @task so they are not re-run on resume (D-04).
#   6. Nodes must be idempotent up to any interrupt(): write the DecisionRequest through DecisionBroker first, then call interrupt() (D-06).
#   7. Pass thread_id = the run or node id; use the SqliteSaver from checkpoints.db with durability="sync" (D-05).
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/planning/test_planner_graph.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/planning/planner_graph.py` and `uv run mypy src/asf/m3_orchestration/planning/planner_graph.py` are clean.

from typing import Any


def build_planner_graph(checkpointer: Any) -> Any:
    raise NotImplementedError
