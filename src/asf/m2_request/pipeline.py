# FILE: src/asf/m2_request/pipeline.py
# ROLE: The M2 LangGraph graph: intake branches -> barrier -> normalise -> understand.
# ARCH REF: M2; p03; D-04
# OWNS: Graph wiring for M2
# DOES NOT OWN: The step logic (sibling files)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m2_request/document_ingestion.py: ingest_document (step)
#   - imports from src/asf/m2_request/repository_intake.py: intake_repository (step)
#   - imports from src/asf/m2_request/prompt_normalisation.py: normalise_prompt (step)
#   - imports from src/asf/m2_request/request_understanding.py: understand_request (step)
#   - called by src/asf/m2_request/intake_router.py: build_request_graph
#   - called by tests/m2_request/test_pipeline.py: build_request_graph
#   - emits/consumes: emits narrative events TASK_RECEIVED, STEP_STARTED, HANDOFF_SENT, HANDOFF_RECEIVED (with causation_id set to the triggering event) via StateStore.commit
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
# DONE WHEN: (1) tests/m2_request/test_pipeline.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m2_request/pipeline.py` and `uv run mypy src/asf/m2_request/pipeline.py` are clean.

from typing import Any


def build_request_graph(checkpointer: Any) -> Any:
    """Return the compiled M2 StateGraph."""
    raise NotImplementedError
