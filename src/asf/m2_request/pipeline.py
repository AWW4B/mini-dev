# FILE: src/asf/m2_request/pipeline.py
# ROLE: The M2 LangGraph graph: intake branches -> barrier -> normalise -> understand.
# ARCH REF: M2; p03; D-04
# OWNS: Graph wiring for M2
# DOES NOT OWN: The step logic (sibling files)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m2_request/document_ingestion.py: ingest_document (step), DocumentNotIngestible (unreadable attachment -> ask the requester)
#   - imports from src/asf/contracts/decisions.py: DecisionRequest (IF-03 requests written through the DecisionBroker)
#   - imports from src/asf/contracts/errors.py: PolicyDenied (the requester aborted)
#   - imports from src/asf/contracts/events.py: EventEnvelope, EventKind (narrative events)
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

import logging
import operator
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, TypedDict, cast

from langgraph.config import get_config
from langgraph.func import task
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from asf.contracts.decisions import DecisionRequest
from asf.contracts.errors import PolicyDenied
from asf.contracts.events import EventEnvelope, EventKind
from asf.m2_request.document_ingestion import DocumentNotIngestible, ingest_document
from asf.m2_request.prompt_normalisation import normalise_prompt
from asf.m2_request.repository_intake import intake_repository
from asf.m2_request.request_understanding import understand_request

logger = logging.getLogger(__name__)

_REQUESTER = "asf.m2_request.pipeline"


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
    # Narrative events (JSON), collected by every node and written to the outbox by the single-threaded nodes
    events: Annotated[list[str], operator.add]
    # Optional runtime dependencies
    gateway: Any
    skills: Any
    decision_broker: Any
    state_store: Any


def _in_graph_context() -> bool:
    try:
        get_config()
    except RuntimeError:
        return False
    return True


def _dependency(state: PipelineState, name: str) -> Any:
    """A live runtime dependency (gateway, skills, decision_broker, state_store).

    Pass them in ``config["configurable"]`` when the graph has a checkpointer: live objects in the state cannot be
    serialised into a checkpoint. Values placed directly in the state are still honoured for uncheckpointed runs.
    """
    value = cast(Mapping[str, Any], state).get(name)
    if value is None and _in_graph_context():
        value = get_config().get("configurable", {}).get(name)
    return value


def _narrative_event(
    state: PipelineState,
    kind: EventKind,
    name: str,
    payload: dict[str, Any],
    caused_by: str | None = None,
) -> list[str]:
    """One narrative event as JSON; ids are derived from the request id so a resumed node cannot duplicate them."""
    run_id = state.get("request_id", "")
    event = EventEnvelope.model_validate(
        {
            "event_id": f"evt-{run_id}-{name}",
            "run_id": run_id,
            "seq": 0,  # the event log assigns the real sequence number
            "ts": datetime.now(UTC),
            "actor": {"kind": "service", "role": "intake", "name": "Request intake"},
            "kind": kind,
            "causation_id": f"evt-{run_id}-{caused_by}" if caused_by else None,
            "correlation_id": run_id,
            "payload": payload,
        }
    )
    return [event.model_dump_json()]


def _flush_events(state: PipelineState, new_events: list[str]) -> None:
    """Write the collected events to the StateStore outbox (the table StateStore.commit writes events to).

    Only call this from a node that runs alone in its graph step (the barrier and later nodes): the SQLite
    connection belongs to the caller's thread and the parallel intake branches run in worker threads.
    """
    store = _dependency(state, "state_store")
    events = [*state.get("events", []), *new_events]
    if store is None or getattr(store, "readonly", False) or not events:
        return
    now_iso = datetime.now(UTC).isoformat()
    rows = []
    for raw in events:
        envelope = EventEnvelope.model_validate_json(raw)
        rows.append((str(envelope.event_id), str(envelope.run_id), raw, now_iso))
    try:
        with store.conn:
            store.conn.executemany(
                "INSERT OR IGNORE INTO outbox (event_id, run_id, payload, published, created_at) VALUES (?, ?, ?, 0, ?)",
                rows,
            )
    except sqlite3.Error:
        logger.warning("could not record %d narrative events for request %s", len(rows), state.get("request_id", ""), exc_info=True)


@task
def _task_ingest_document(path_str: str) -> tuple[Any, str]:
    doc = ingest_document(Path(path_str))
    return doc, str(getattr(doc, "markdown_ref", path_str))


@task
def _task_intake_repo(repo_ref: str, project_id: str) -> Any:
    return intake_repository(repo_ref, project_id)


def _run_task(task_obj: Any, *args: Any) -> Any:
    """Run a @task inside the graph (so it is checkpointed and not re-run on resume), or plainly outside it."""
    if _in_graph_context():
        return task_obj(*args).result()
    return getattr(task_obj, "func", task_obj)(*args)


def _ask_requester(state: PipelineState, request: DecisionRequest) -> str | None:
    """Write the decision through the DecisionBroker first, then interrupt (D-06); None when no broker is wired in."""
    broker = _dependency(state, "decision_broker")
    if broker is None:
        return None
    broker.request(request)
    answer = interrupt({"decision_id": request.decision_id, "question": request.question, "options": request.options})
    return str(answer)


def _step_ingest_docs(state: PipelineState) -> dict[str, Any]:
    document_refs: list[str] = []
    ingested_docs: list[Any] = []
    request_id = state.get("request_id", "")

    for position, ref in enumerate(state.get("attachment_refs", [])):
        path = Path(str(ref))
        if not path.is_file():
            document_refs.append(str(ref))  # not a local file (for example a blob ref): pass it through untouched
            continue
        try:
            doc, markdown_ref = _run_task(_task_ingest_document, str(path))
        except DocumentNotIngestible as err:
            answer = _ask_requester(state, err.decision_request(run_id=request_id, decision_id=f"dec-document-{request_id}-{position}"))
            if answer != "skip_document":
                raise
            logger.warning("skipping document %s at the requester's request: %s", path.name, err.reason)
            continue
        ingested_docs.append(doc)
        document_refs.append(markdown_ref)

    events = _narrative_event(
        state, EventKind.TASK_RECEIVED, "task_received", {"goal_summary": str(state.get("prompt", ""))[:200], "from_role": "user"}
    ) + _narrative_event(
        state,
        EventKind.STEP_STARTED,
        "ingest_docs",
        {"step_no": 1, "strategy": "document_ingestion", "summary": f"{len(document_refs)} attachment(s)"},
        caused_by="task_received",
    )
    return {"ingested_documents": ingested_docs, "document_refs": document_refs, "events": events}


def _step_intake_repo(state: PipelineState) -> dict[str, Any]:
    repo_ref = state.get("repo_ref")
    repo_profile = _run_task(_task_intake_repo, str(repo_ref), str(state.get("project_id", "default"))) if repo_ref else None
    events = _narrative_event(
        state,
        EventKind.STEP_STARTED,
        "intake_repo",
        {"step_no": 1, "strategy": "repository_intake", "summary": "repository profiled" if repo_ref else "no repository attached"},
        caused_by="task_received",
    )
    return {"repo_profile": repo_profile, "events": events}


def _step_barrier(state: PipelineState) -> dict[str, Any]:
    """Brings the two intake branches together; runs alone, so it is the first safe point to write events."""
    events = _narrative_event(
        state, EventKind.HANDOFF_SENT, "handoff_sent", {"to_role": "normaliser", "summary": "intake branches finished"}, caused_by="task_received"
    )
    _flush_events(state, events)
    return {"events": events}


def _step_normalise(state: PipelineState) -> dict[str, Any]:
    normalised = normalise_prompt(state.get("prompt", ""), gateway=_dependency(state, "gateway"))
    events = _narrative_event(
        state,
        EventKind.STEP_STARTED,
        "normalise",
        {"step_no": 2, "strategy": "prompt_normalisation", "summary": "prompt cleaned"},
        caused_by="handoff_sent",
    )
    _flush_events(state, events)
    return {"normalized_prompt": normalised, "events": events}


def _confirm_unsupported_repository(state: PipelineState) -> None:
    profile = state.get("repo_profile")
    if profile is None or getattr(profile, "supported", True):
        return
    request_id = state.get("request_id", "")
    request = DecisionRequest.model_validate(
        {
            "decision_id": f"dec-unsupported-{request_id}",
            "run_id": request_id,
            "kind": "clarify",
            "requester": _REQUESTER,
            "question": "The attached repository is not supported (missing, or no supported language). Continue without repository context?",
            "options": ["abort", "proceed_anyway"],
            "default_on_timeout": None,
        }
    )
    answer = _ask_requester(state, request)
    if answer is None:
        logger.warning("repository for request %s is unsupported and no DecisionBroker is attached; continuing without it", request_id)
    elif answer == "abort":
        raise PolicyDenied("The requester aborted: the attached repository is not supported.")


def _step_understand(state: PipelineState) -> dict[str, Any]:
    _confirm_unsupported_repository(state)

    structured = understand_request(
        request_id=state.get("request_id", "req-default"),
        prompt=state.get("normalized_prompt") or state.get("prompt", ""),
        document_refs=state.get("document_refs", []),
        repo_profile=state.get("repo_profile"),
        gateway=_dependency(state, "gateway"),
        skills=_dependency(state, "skills"),
        project_id=state.get("project_id", "default"),
    )

    events = _narrative_event(
        state,
        EventKind.STEP_STARTED,
        "understand",
        {"step_no": 3, "strategy": "request_understanding", "summary": "requirements extracted"},
        caused_by="handoff_sent",
    ) + _narrative_event(
        state, EventKind.HANDOFF_RECEIVED, "handoff_received", {"to_role": "orchestrator", "summary": "structured request ready"}, caused_by="handoff_sent"
    )
    _flush_events(state, events)
    return {"structured_request": structured, "events": events}


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
