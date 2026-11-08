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

from pydantic import BaseModel

from asf.contracts.events import EventEnvelope


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


def build_narrative(events: list[EventEnvelope]) -> list[NarrativeItem]:
    raise NotImplementedError


def derive_handoffs(events: list[EventEnvelope]) -> list[Handoff]:
    raise NotImplementedError
