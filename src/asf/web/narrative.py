# FILE: src/asf/web/narrative.py
# ROLE: Builds the per-role step-by-step narrative from structured events; hand-offs are derived from causation IDs. No LLM writes narrative text.
# ARCH REF: M1; p02 Active Group Chat; p15 EventEnvelope; IF-18; D-14b narrative amendment
# OWNS: Narrative items and hand-off derivation
# DOES NOT OWN: Event storage; HTML
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/events.py: EventEnvelope, EventKind (narrative kinds)
#   - imports from src/asf/m5_shared/events/redaction.py: redact_text (redaction)
#   - called by src/asf/web/projection.py: build_narrative, NarrativeItem
#   - called by tests/web/test_narrative.py: NarrativeItem, Handoff, build_narrative, derive_handoffs
#   - emits/consumes: consumes TASK_RECEIVED, STEP_STARTED, TOOL_CALLED, TOOL_RESULT, HANDOFF_SENT, HANDOFF_RECEIVED, GATE_RESULT, DECISION_NEEDED
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. A hand-off pair is HANDOFF_SENT plus the HANDOFF_RECEIVED whose causation_id equals the sent event_id.
#   6. Summaries are template strings filled from payload fields; never call a model.
#   7. Redact every text field; HTML escaping happens in the browser and in server JSON encoding.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/web/test_narrative.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/web/narrative.py` and `uv run mypy src/asf/web/narrative.py` are clean.

from typing import Any

from pydantic import BaseModel

from asf.contracts.events import EventEnvelope, EventKind, Visibility
from asf.m5_shared.events.redaction import redact_text


class NarrativeItem(BaseModel):
    seq: int
    participant: str
    kind: str
    summary: str
    detail_ref: str | None = None
    internal: bool = False


class Handoff(BaseModel):
    from_participant: str
    to_participant: str
    task_id: str | None
    sent_seq: int
    received_seq: int | None


def _get(payload: dict[str, Any], key: str, default: str = "?") -> str:
    value = payload.get(key)
    return default if value is None or value == "" else str(value)


def _task_received(p: dict[str, Any]) -> str:
    return f"received a task from {_get(p, 'from_role')}: {_get(p, 'goal_summary')}"


def _step_started(p: dict[str, Any]) -> str:
    return f"started step {_get(p, 'step_no')} ({_get(p, 'strategy')}): {_get(p, 'summary', '')}".rstrip(": ")


def _tool_called(p: dict[str, Any]) -> str:
    via = " via code" if p.get("via_code_exec") else ""
    reason = f" because {p['reason']}" if p.get("reason") else ""
    return f"called {_get(p, 'tool')}{via} ({_get(p, 'args_summary', 'no arguments')}){reason}: {_get(p, 'status')}, sandbox {_get(p, 'sandbox_tier')}"


def _tool_result(p: dict[str, Any]) -> str:
    exit_status = f", exit {p['exit_status']}" if p.get("exit_status") is not None else ""
    return f"{_get(p, 'tool')} finished in {_get(p, 'duration_ms', '0')} ms{exit_status}: {_get(p, 'summary', '')}".rstrip(": ")


def _handoff_sent(p: dict[str, Any]) -> str:
    return f"handed over to {_get(p, 'to_role')}: {_get(p, 'summary', '')}".rstrip(": ")


def _handoff_received(p: dict[str, Any]) -> str:
    return f"received the hand-off: {_get(p, 'summary', '')}".rstrip(": ")


def _gate_result(p: dict[str, Any]) -> str:
    verdict = "passed" if p.get("passed") else "failed"
    failure = f" ({p['failure_class']})" if p.get("failure_class") else ""
    return f"gate {verdict}{failure}: {_get(p, 'summary', '')}".rstrip(": ")


def _decision_needed(p: dict[str, Any]) -> str:
    return f"needs a decision ({_get(p, 'kind')}): {_get(p, 'question')}"


# Summaries are templates over structured payload fields: no model ever writes narrative text.
_TEMPLATES = {
    EventKind.TASK_RECEIVED: _task_received,
    EventKind.STEP_STARTED: _step_started,
    EventKind.TOOL_CALLED: _tool_called,
    EventKind.TOOL_RESULT: _tool_result,
    EventKind.HANDOFF_SENT: _handoff_sent,
    EventKind.HANDOFF_RECEIVED: _handoff_received,
    EventKind.GATE_RESULT: _gate_result,
    EventKind.DECISION_NEEDED: _decision_needed,
}


def _detail_ref(event: EventEnvelope) -> str | None:
    p = event.payload
    for key in ("output_ref", "report_ref", "diff_ref", "evidence_ref"):
        if p.get(key):
            return str(p[key])
    return event.payload_ref


def build_narrative(events: list[EventEnvelope]) -> list[NarrativeItem]:
    """One item per narrative event, in seq order. Every text field is redacted; HTML escaping happens in the browser."""
    items: list[NarrativeItem] = []
    for event in sorted(events, key=lambda e: e.seq):
        template = _TEMPLATES.get(event.kind)
        if template is None:
            continue  # model calls, usage and other plumbing are not part of the story
        items.append(
            NarrativeItem(
                seq=event.seq,
                participant=redact_text(event.actor.name),
                kind=event.kind.value,
                summary=redact_text(template(event.payload)),
                detail_ref=_detail_ref(event),
                internal=event.visibility is Visibility.INTERNAL,
            )
        )
    return items


def derive_handoffs(events: list[EventEnvelope]) -> list[Handoff]:
    """Pair each HANDOFF_SENT with the HANDOFF_RECEIVED whose causation_id is its event_id; unmatched sends stay open."""
    received_by_cause = {str(e.causation_id): e for e in events if e.kind is EventKind.HANDOFF_RECEIVED and e.causation_id is not None}
    handoffs: list[Handoff] = []
    for event in sorted(events, key=lambda e: e.seq):
        if event.kind is not EventKind.HANDOFF_SENT:
            continue
        received = received_by_cause.get(str(event.event_id))
        to_name = redact_text(received.actor.name) if received is not None else redact_text(str(event.payload.get("to_role") or "?"))
        handoffs.append(
            Handoff(
                from_participant=redact_text(event.actor.name),
                to_participant=to_name,
                task_id=str(event.task_id) if event.task_id is not None else None,
                sent_seq=event.seq,
                received_seq=received.seq if received is not None else None,
            )
        )
    return handoffs
