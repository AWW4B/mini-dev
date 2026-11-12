# FILE: src/asf/contracts/events.py
# ROLE: Defines EventEnvelope and every event kind, including the narrative kinds the web chat renders.
# ARCH REF: p15 EventEnvelope; IF-17 EventPublish; IF-18 EventSubscribe; D-14b narrative; D-23
# OWNS: Event kinds, envelope fields, narrative payload models
# DOES NOT OWN: Writing or reading events (src/asf/m5_shared/events/event_log.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/ids.py: EventId, RunId, TaskId (typed ids)
#   - called by src/asf/contracts/state.py: EventEnvelope
#   - called by src/asf/m5_shared/events/event_log.py: EventEnvelope, Visibility
#   - called by src/asf/m5_shared/events/fanout.py: EventEnvelope, EventKind
#   - called by src/asf/cli/views/trace_view.py: EventEnvelope, Visibility
#   - called by src/asf/web/narrative.py: EventEnvelope, EventKind
#   - called by src/asf/m2_request/pipeline.py: EventEnvelope, EventKind
#   - called by src/asf/m2_request/intake_router.py: EventEnvelope, EventKind
#   - called by tests/contracts/test_events.py: EventKind, Visibility, Actor, EventEnvelope, TaskReceivedPayload, StepStartedPayload, ToolCalledPayload, ToolResultPayload, HandoffPayload, GateResultPayload, DecisionNeededPayload
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. This file is declarations only: Pydantic models, enums and type aliases. Add field validators only where the docstring of a field states a constraint.
#   6. Every model must round-trip through model_dump_json() / model_validate_json() unchanged; the JSON Schema exported from these models is the published contract (D-39: no hand-written JSON).
#   7. Changing a field name or type is a contract change: stop and report instead.
#   8. Narrative kinds (TASK_RECEIVED, STEP_STARTED, TOOL_CALLED, TOOL_RESULT, HANDOFF_SENT, HANDOFF_RECEIVED, GATE_RESULT, DECISION_NEEDED) are built from structured data by the emitting module, never written by an LLM.
#   9. Hand-offs are represented only by causation_id links plus HANDOFF_* events; agents never message each other through events.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; business logic; I/O; imports from asf.m1-m5 packages, asf.cli, asf.web or asf.platform
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/contracts/test_events.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/contracts/events.py` and `uv run mypy src/asf/contracts/events.py` are clean.

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from asf.contracts.ids import EventId, RunId, TaskId


class EventKind(StrEnum):
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_RECOVERED = "run_recovered"
    STATE_CHANGED = "state_changed"
    MODEL_CALL = "model_call"
    USAGE = "usage"
    CONTRACT_CHANGED = "contract_changed"
    SLOT_FREE = "slot_free"
    LIMIT_HIT = "limit_hit"
    CANCELLED = "cancelled"
    DECISION_RESOLVED = "decision_resolved"
    # narrative kinds rendered by the read-only web chat (D-14b)
    TASK_RECEIVED = "task_received"
    STEP_STARTED = "step_started"
    TOOL_CALLED = "tool_called"
    TOOL_RESULT = "tool_result"
    HANDOFF_SENT = "handoff_sent"
    HANDOFF_RECEIVED = "handoff_received"
    GATE_RESULT = "gate_result"
    DECISION_NEEDED = "decision_needed"


class Visibility(StrEnum):
    USER = "user"
    INTERNAL = "internal"


class Actor(BaseModel):
    kind: Literal["agent", "service", "user"]
    role: str = Field(description="e.g. planner, decomposer, worker, gate, integrator, scheduler")
    name: str = Field(description="display name shown as a chat participant")
    model_tier: str | None = Field(default=None, description="T0/T1/T2/T3/reviewer when a model acted")


class EventEnvelope(BaseModel):
    event_id: EventId
    run_id: RunId
    task_id: TaskId | None = None
    seq: int = Field(description="monotonic per run; the replay cursor")
    ts: datetime
    actor: Actor
    kind: EventKind
    causation_id: EventId | None = Field(default=None, description="event that caused this one; hand-offs are derived from it")
    correlation_id: str
    payload: dict[str, Any] = Field(default_factory=dict, description="small payload, already redacted")
    payload_ref: str | None = Field(default=None, description="blob ref for payloads over 8 KB")
    visibility: Visibility = Visibility.USER
    redacted: bool = True


class TaskReceivedPayload(BaseModel):
    goal_summary: str
    from_role: str


class StepStartedPayload(BaseModel):
    step_no: int
    strategy: str
    summary: str


class ToolCalledPayload(BaseModel):
    tool: str
    args_summary: str
    reason: str | None = None
    status: Literal["approved", "denied", "pending_approval"]
    sandbox_tier: Literal["A", "B", "C", "none"]
    via_code_exec: bool = False


class ToolResultPayload(BaseModel):
    tool: str
    summary: str
    exit_status: int | None = None
    duration_ms: int
    output_ref: str | None = None


class HandoffPayload(BaseModel):
    to_role: str
    to_task: TaskId | None = None
    summary: str


class GateResultPayload(BaseModel):
    passed: bool
    failure_class: str | None = None
    summary: str
    report_ref: str | None = None


class DecisionNeededPayload(BaseModel):
    decision_id: str
    kind: str
    question: str
