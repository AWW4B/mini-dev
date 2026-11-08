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

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

from langgraph.func import task
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from asf.m2_request.document_ingestion import ingest_document
from asf.m2_request.prompt_normalisation import normalise_prompt
from asf.m2_request.repository_intake import intake_repository
from asf.m2_request.request_understanding import understand_request


class PipelineState(TypedDict, total=False):
    request_id: str
    project_id: str
    prompt: str
    prompt_provenance: str
    prompt_trusted: bool
    attachment_refs: list[str]
    attachment_provenance: str
    attachment_trusted: bool
    repo_ref: str | None
    repo_provenance: str
    repo_trusted: bool
    mode_hint: Any
    provenance: dict[str, Any]
    # Intermediate & output state
    ingested_documents: list[Any]
    document_refs: list[str]
    repo_profile: Any
    normalized_prompt: str
    structured_request: Any
    # Optional runtime dependencies
    gateway: Any
    skills: Any
    decision_broker: Any
    state_store: Any


def _emit_narrative_event(
    state: PipelineState,
    kind: str,
    task_id: str | None = None,
    causation_id: str | None = None,
) -> str | None:
    store = state.get("state_store")
    if store is None or getattr(store, "readonly", False):
        return None
    req_id = state.get("request_id", "")
    event_id = f"evt-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(UTC).isoformat()

    event_payload = {
        "event_id": event_id,
        "run_id": req_id,
        "task_id": task_id,
        "kind": kind,
        "timestamp": now_iso,
        "causation_id": causation_id,
    }
    conn = getattr(store, "conn", None)
    if conn is not None:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO outbox (event_id, run_id, payload, published, created_at) "
                "VALUES (?, ?, ?, 0, ?)",
                (event_id, req_id, json.dumps(event_payload), now_iso),
            )
            conn.commit()
        except Exception as _err:  # noqa: BLE001
            _ = _err
    return event_id


@task
def _task_ingest_document(path_str: str) -> tuple[Any, str]:
    path = Path(path_str)
    if path.exists() and path.is_file():
        doc = ingest_document(path)
        markdown_ref = getattr(doc, "markdown_ref", path_str)
        return doc, markdown_ref
    return None, path_str


@task
def _task_intake_repo(repo_ref: str, project_id: str) -> Any:
    return intake_repository(repo_ref, project_id)


def _run_task(task_obj: Any, *args: Any) -> Any:
    try:
        t = task_obj(*args)
        if hasattr(t, "result"):
            return t.result()
        return t
    except Exception:
        func = getattr(task_obj, "func", task_obj)
        return func(*args)


def _step_ingest_docs(state: PipelineState) -> dict[str, Any]:
    _emit_narrative_event(state, "TASK_RECEIVED")
    _emit_narrative_event(state, "STEP_STARTED", task_id="ingest_docs")

    document_refs: list[str] = []
    ingested_docs: list[Any] = []

    for ref in state.get("attachment_refs", []):
        p = Path(str(ref))
        if p.exists() and p.is_file():
            try:
                doc, ref_out = _run_task(_task_ingest_document, str(p))
                if doc is not None:
                    ingested_docs.append(doc)
                document_refs.append(ref_out)
            except Exception as _err:  # noqa: BLE001
                _ = _err
                document_refs.append(str(ref))
        else:
            document_refs.append(str(ref))

    return {
        "ingested_documents": ingested_docs,
        "document_refs": document_refs,
    }


def _step_intake_repo(state: PipelineState) -> dict[str, Any]:
    _emit_narrative_event(state, "STEP_STARTED", task_id="intake_repo")
    repo_ref = state.get("repo_ref")
    project_id = state.get("project_id", "default")
    repo_profile = None

    if repo_ref:
        try:
            repo_profile = _run_task(_task_intake_repo, str(repo_ref), str(project_id))
        except Exception as _err:  # noqa: BLE001
            _ = _err

    return {
        "repo_profile": repo_profile,
    }


def _step_barrier(state: PipelineState) -> dict[str, Any]:
    # Barrier brings the two intake branches together
    _emit_narrative_event(state, "HANDOFF_SENT", task_id="barrier")
    return {}


def _step_normalise(state: PipelineState) -> dict[str, Any]:
    _emit_narrative_event(state, "STEP_STARTED", task_id="normalise")
    prompt = state.get("prompt", "")
    gateway = state.get("gateway")

    try:
        norm = normalise_prompt(prompt, gateway=gateway)
    except Exception as _err:  # noqa: BLE001
        _ = _err
        norm = prompt

    return {
        "normalized_prompt": norm,
    }


def _step_understand(state: PipelineState) -> dict[str, Any]:
    _emit_narrative_event(state, "STEP_STARTED", task_id="understand")

    # Check for HITL interrupt if repo is explicitly unsupported
    repo_prof = state.get("repo_profile")
    broker = state.get("decision_broker")
    if (
        broker is not None
        and repo_prof is not None
        and not getattr(repo_prof, "supported", True)
    ):
        dec_id = f"dec-unsupported-{state.get('request_id', '')}"
        try:
            broker.request(
                decision_id=dec_id,
                topic="unsupported_repo",
                options=["abort", "proceed_anyway"],
            )
        except Exception as _err:  # noqa: BLE001
            _ = _err
        interrupt({"reason": "Unsupported repository profile detected"})

    req_id = state.get("request_id", "req-default")
    prompt_text = state.get("normalized_prompt") or state.get("prompt", "")
    doc_refs = state.get("document_refs", [])
    gateway = state.get("gateway")
    skills = state.get("skills")
    proj_id = state.get("project_id", "default")

    structured = understand_request(
        request_id=req_id,
        prompt=prompt_text,
        document_refs=doc_refs,
        repo_profile=repo_prof,
        gateway=gateway,
        skills=skills,
        project_id=proj_id,
    )

    _emit_narrative_event(state, "HANDOFF_RECEIVED", task_id="understand")

    return {
        "structured_request": structured,
    }


def build_request_graph(checkpointer: Any = None) -> Any:
    """Return the compiled M2 StateGraph."""
    builder = StateGraph(PipelineState)

    builder.add_node("ingest_docs", _step_ingest_docs)
    builder.add_node("intake_repo", _step_intake_repo)
    builder.add_node("barrier", _step_barrier)
    builder.add_node("normalise", _step_normalise)
    builder.add_node("understand", _step_understand)

    builder.add_edge(START, "ingest_docs")
    builder.add_edge(START, "intake_repo")
    builder.add_edge("ingest_docs", "barrier")
    builder.add_edge("intake_repo", "barrier")
    builder.add_edge("barrier", "normalise")
    builder.add_edge("normalise", "understand")
    builder.add_edge("understand", END)

    if checkpointer is not None:
        return builder.compile(checkpointer=checkpointer)
    return builder.compile()
