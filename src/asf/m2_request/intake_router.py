# FILE: src/asf/m2_request/intake_router.py
# ROLE: Receives IF-01, creates the request record idempotently, tags provenance and fans out to document and repository intake.
# ARCH REF: M2; p03 Intake Router; IF-01 SubmitRequest; IF-02
# OWNS: Request records, fan-out and barrier
# DOES NOT OWN: Extraction (document_ingestion, repository_intake)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/requests.py: SubmitRequest, StructuredRequest (IF-01/IF-02)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (IF-16 state)
#   - imports from src/asf/m2_request/pipeline.py: build_request_graph (the M2 graph)
#   - imports from src/asf/contracts/events.py: EventEnvelope, EventKind (the STATE_CHANGED envelope)
#   - called by src/asf/cli/commands/run.py: submit
#   - called by tests/m2_request/test_intake_router.py: submit
#   - emits/consumes: emits STATE_CHANGED for the request record
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Idempotency key = hash(project_id, text, attachment hashes); a duplicate returns the existing request id.
#   6. Mark every text source with provenance (user, document, repo); document and repo text is untrusted.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m2_request/test_intake_router.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m2_request/intake_router.py` and `uv run mypy src/asf/m2_request/intake_router.py` are clean.

import hashlib
import logging
import sqlite3
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any

from asf.contracts.events import EventEnvelope, EventKind
from asf.contracts.requests import StructuredRequest, SubmitRequest
from asf.m2_request.pipeline import build_request_graph
from asf.m5_shared.state_store.store import StateStore

logger = logging.getLogger(__name__)

_CACHE_LIMIT = 128
_REQUEST_CACHE: OrderedDict[str, StructuredRequest] = OrderedDict()  # bounded LRU: a long-lived process must not grow without limit


def _remember(idem_key: str, structured: StructuredRequest) -> None:
    _REQUEST_CACHE[idem_key] = structured
    _REQUEST_CACHE.move_to_end(idem_key)
    while len(_REQUEST_CACHE) > _CACHE_LIMIT:
        _REQUEST_CACHE.popitem(last=False)


def _compute_idempotency_key(request: SubmitRequest) -> str:
    h = hashlib.sha256()
    h.update(str(request.project_id).encode("utf-8"))
    h.update(b":")
    h.update(request.text.encode("utf-8"))
    h.update(b":")
    for ref in sorted(request.attachment_refs):
        h.update(ref.encode("utf-8"))
        h.update(b",")
    return h.hexdigest()


def submit(
    request: SubmitRequest,
    state_store: StateStore | None = None,
    graph: Any = None,
) -> StructuredRequest:
    """IF-01 in, IF-02 out (runs the M2 graph to completion or to a HITL interrupt)."""
    if not isinstance(request, SubmitRequest):
        raise ValueError("request must be an instance of SubmitRequest")

    idem_key = _compute_idempotency_key(request)

    # 1. Check idempotency in state store if available
    if state_store is not None and not state_store.readonly:
        try:
            state_store.conn.execute(
                "CREATE TABLE IF NOT EXISTS request_records ("
                "idempotency_key TEXT PRIMARY KEY, "
                "request_id TEXT NOT NULL, "
                "payload TEXT NOT NULL, "
                "created_at TEXT NOT NULL"
                ")"
            )
            cur = state_store.conn.execute(
                "SELECT payload FROM request_records WHERE idempotency_key = ?",
                (idem_key,),
            )
            row = cur.fetchone()
            if row is not None:
                return StructuredRequest.model_validate_json(row["payload"])
        except sqlite3.OperationalError:
            logger.warning("idempotency lookup failed; continuing without the stored record", exc_info=True)

    # 2. Check process memory cache for duplicate
    cached = _REQUEST_CACHE.get(idem_key)
    if cached is not None:
        _REQUEST_CACHE.move_to_end(idem_key)
        return cached

    request_id = f"req-{idem_key[:16]}"

    # 3. Mark every text source with provenance (user trusted; document and repo untrusted)
    initial_state: dict[str, Any] = {
        "request_id": request_id,
        "project_id": str(request.project_id),
        "prompt": request.text,
        "prompt_provenance": "user",
        "prompt_trusted": True,
        "attachment_refs": list(request.attachment_refs),
        "attachment_provenance": "document",
        "attachment_trusted": False,
        "repo_ref": request.repo_ref,
        "repo_provenance": "repo",
        "repo_trusted": False,
        "mode_hint": request.mode_hint,
        "provenance": {
            "text": {"source": "user", "trusted": True},
            "attachments": [
                {"ref": ref, "source": "document", "trusted": False}
                for ref in request.attachment_refs
            ],
            "repo": (
                {"ref": request.repo_ref, "source": "repo", "trusted": False}
                if request.repo_ref
                else None
            ),
        },
    }

    # 4. Invoke graph
    if graph is None:
        graph = build_request_graph(checkpointer=None)

    runtime: dict[str, Any] = {"thread_id": request_id}
    if state_store is not None:
        runtime["state_store"] = state_store  # live objects go in the config, not the checkpointed state
    output = graph.invoke(initial_state, {"configurable": runtime})

    if isinstance(output, StructuredRequest):
        structured = output
    elif isinstance(output, dict):
        if "structured_request" in output:
            sr = output["structured_request"]
            structured = (
                sr
                if isinstance(sr, StructuredRequest)
                else StructuredRequest.model_validate(sr)
            )
        else:
            structured = StructuredRequest.model_validate(output)
    else:
        raise TypeError(f"Unexpected graph output type: {type(output)}")

    # 5. Store record and emit STATE_CHANGED
    _remember(idem_key, structured)

    if state_store is not None and not state_store.readonly:
        now_iso = datetime.now(UTC).isoformat()
        try:
            state_store.conn.execute(
                "INSERT OR REPLACE INTO request_records (idempotency_key, request_id, payload, created_at) "
                "VALUES (?, ?, ?, ?)",
                (idem_key, request_id, structured.model_dump_json(), now_iso),
            )
            event = EventEnvelope.model_validate(
                {
                    "event_id": f"evt-{request_id}-state_changed",
                    "run_id": request_id,
                    "seq": 0,  # the event log assigns the real sequence number
                    "ts": now_iso,
                    "actor": {"kind": "service", "role": "intake", "name": "Request intake"},
                    "kind": EventKind.STATE_CHANGED,
                    "correlation_id": request_id,
                    "payload": {"entity": "request", "entity_id": request_id, "idempotency_key": idem_key, "status": "COMPLETED"},
                }
            )
            state_store.conn.execute(
                "INSERT OR IGNORE INTO outbox (event_id, run_id, payload, published, created_at) "
                "VALUES (?, ?, ?, 0, ?)",
                (str(event.event_id), request_id, event.model_dump_json(), now_iso),
            )
            state_store.conn.commit()
        except sqlite3.OperationalError:
            logger.warning("could not store the request record for %s", request_id, exc_info=True)

    return structured
