# FILE: src/asf/m3_orchestration/decomposition/decomposition_graph.py
# ROLE: Recursive Decomposition Engine graph: batched loop over the frontier, sizing, splitting, certification and dispatch.
# ARCH REF: M3; p05; IF-07a; IF-09; IF-10; IF-10b; D-06
# OWNS: Decomposition loop and report
# DOES NOT OWN: Executing leaves (M4)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/outcomes.py: ApprovedPlan, DecompositionReport, TaskOutcome (IF-07a/IF-10b/IF-10)
#   - imports from src/asf/m3_orchestration/decomposition/frontier.py: Frontier (frontier)
#   - imports from src/asf/m3_orchestration/decomposition/sizer.py: estimate_size, fits_leaf (sizing)
#   - imports from src/asf/m3_orchestration/decomposition/rubric.py: score_node (rubric)
#   - imports from src/asf/m3_orchestration/decomposition/splitter.py: propose_split (split)
#   - imports from src/asf/m3_orchestration/decomposition/split_validator.py: validate_split (validation)
#   - imports from src/asf/m3_orchestration/decomposition/leaf_certifier.py: certify_leaf (leaf)
#   - imports from src/asf/m3_orchestration/lifecycle.py: transition (state machine)
#   - imports from src/asf/m4_execution/scheduler.py: TaskScheduler (IF-09 enqueue)
#   - called by src/asf/m3_orchestration/run_graph.py: build_decomposition_graph
#   - called by tests/m3_orchestration/decomposition/test_decomposition_graph.py: build_decomposition_graph
#   - emits/consumes: emits node sizing/split events and emits narrative events TASK_RECEIVED, STEP_STARTED, HANDOFF_SENT, HANDOFF_RECEIVED (with causation_id set to the triggering event) via StateStore.commit
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Build the graph with LangGraph StateGraph; side-effecting steps use the Functional API @task so they are not re-run on resume (D-04).
#   6. Nodes must be idempotent up to any interrupt(): write the DecisionRequest through DecisionBroker first, then call interrupt() (D-06).
#   7. Pass thread_id = the run or node id; use the SqliteSaver from checkpoints.db with durability="sync" (D-05).
#   8. Loop in batches over the persisted frontier; check pause/budget flags each iteration.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/decomposition/test_decomposition_graph.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/decomposition/decomposition_graph.py` and `uv run mypy src/asf/m3_orchestration/decomposition/decomposition_graph.py` are clean.

from typing import Any


def build_decomposition_graph(checkpointer: Any) -> Any:
    raise NotImplementedError
