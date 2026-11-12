# FILE: tests/contracts/test_events.py
# ROLE: Tests that prove src/asf/contracts/events.py meets its DONE WHEN conditions.
# ARCH REF: p15 EventEnvelope; IF-17 EventPublish; IF-18 EventSubscribe; D-14b narrative; D-23; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/events.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/events.py: EventKind, Visibility, Actor, EventEnvelope, TaskReceivedPayload, StepStartedPayload, ToolCalledPayload, ToolResultPayload, HandoffPayload, GateResultPayload, DecisionNeededPayload (unit under test)
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use the tmp_path fixture or the fake_paths fixture for every filesystem location.
#   6. Use the fakes from tests/conftest.py instead of real GPUs, networks, sandboxes or model providers unless the test is marked needs_gpu, needs_network or needs_sandbox.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; real API keys; network access in unmarked tests; sleeping for timing (use the fake clock)
# ERRORS: Failures surface as pytest assertion failures.
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_events.py` on Windows and Linux once src/asf/contracts/events.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_events.py` and `uv run mypy tests/contracts/test_events.py` are clean.


from typing import Any

import pytest
from pydantic import ValidationError

from asf.contracts.events import (
    Actor,
    DecisionNeededPayload,
    EventEnvelope,
    EventKind,
    GateResultPayload,
    HandoffPayload,
    StepStartedPayload,
    TaskReceivedPayload,
    ToolCalledPayload,
    ToolResultPayload,
    Visibility,
)


def _actor(**over: Any) -> dict[str, Any]:
    return {"kind": "agent", "role": "worker", "name": "Worker 1", **over}


def _envelope(**over: Any) -> dict[str, Any]:
    return {
        "event_id": "e1",
        "run_id": "r1",
        "seq": 1,
        "ts": "2026-11-12T10:00:00+00:00",
        "actor": _actor(),
        "kind": "task_received",
        "correlation_id": "corr-1",
        **over,
    }


def test_event_kind_values_are_unique_lowercase_and_cover_narrative_kinds() -> None:
    values = [k.value for k in EventKind]
    assert len(values) == len(set(values)) == 19
    assert all(v == v.lower() for v in values)
    for narrative in (
        "task_received", "step_started", "tool_called", "tool_result",
        "handoff_sent", "handoff_received", "gate_result", "decision_needed",
    ):
        assert narrative in values


def test_visibility_values() -> None:
    assert {v.value for v in Visibility} == {"user", "internal"}


def test_actor_kind_is_restricted_and_model_tier_is_optional() -> None:
    assert Actor.model_validate(_actor()).model_tier is None
    assert Actor.model_validate(_actor(kind="user", model_tier="T2")).model_tier == "T2"
    with pytest.raises(ValidationError):
        Actor.model_validate(_actor(kind="robot"))


def test_envelope_defaults() -> None:
    env = EventEnvelope.model_validate(_envelope())
    assert env.visibility is Visibility.USER
    assert env.redacted is True
    assert env.payload == {}
    assert env.payload_ref is None
    assert env.causation_id is None
    assert env.task_id is None


@pytest.mark.parametrize("missing", ["event_id", "run_id", "seq", "ts", "actor", "kind", "correlation_id"])
def test_envelope_required_fields(missing: str) -> None:
    data = _envelope()
    del data[missing]
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate(data)


def test_envelope_rejects_unknown_kind_and_bad_timestamp() -> None:
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate(_envelope(kind="exploded"))
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate(_envelope(ts="yesterday-ish"))


def test_envelope_json_round_trip_keeps_timestamp_and_payload() -> None:
    env = EventEnvelope.model_validate(_envelope(payload={"a": 1, "b": ["x"]}, causation_id="e0", task_id="t1", visibility="internal"))
    again = EventEnvelope.model_validate_json(env.model_dump_json())
    assert again == env
    assert again.ts.tzinfo is not None


def test_envelope_payload_default_is_not_shared() -> None:
    a = EventEnvelope.model_validate(_envelope())
    b = EventEnvelope.model_validate(_envelope())
    a.payload["k"] = 1
    assert b.payload == {}


def test_task_received_and_step_started_payloads() -> None:
    assert TaskReceivedPayload.model_validate({"goal_summary": "g", "from_role": "planner"}).from_role == "planner"
    step = StepStartedPayload.model_validate({"step_no": 2, "strategy": "tool_loop", "summary": "s"})
    assert step.step_no == 2
    with pytest.raises(ValidationError):
        StepStartedPayload.model_validate({"strategy": "tool_loop", "summary": "s"})


def test_tool_called_payload_restricts_status_and_sandbox_tier() -> None:
    base = {"tool": "read_file", "args_summary": "a.py", "status": "approved", "sandbox_tier": "A"}
    ok = ToolCalledPayload.model_validate(base)
    assert ok.via_code_exec is False and ok.reason is None
    for tier in ("A", "B", "C", "none"):
        assert ToolCalledPayload.model_validate({**base, "sandbox_tier": tier}).sandbox_tier == tier
    with pytest.raises(ValidationError):
        ToolCalledPayload.model_validate({**base, "status": "maybe"})
    with pytest.raises(ValidationError):
        ToolCalledPayload.model_validate({**base, "sandbox_tier": "D"})


def test_tool_result_payload_requires_duration() -> None:
    res = ToolResultPayload.model_validate({"tool": "t", "summary": "s", "duration_ms": 5})
    assert res.exit_status is None and res.output_ref is None
    with pytest.raises(ValidationError):
        ToolResultPayload.model_validate({"tool": "t", "summary": "s"})


def test_handoff_payload_target_task_is_optional() -> None:
    assert HandoffPayload.model_validate({"to_role": "gate", "summary": "s"}).to_task is None
    assert HandoffPayload.model_validate({"to_role": "gate", "summary": "s", "to_task": "t2"}).to_task == "t2"


def test_gate_result_payload() -> None:
    passed = GateResultPayload.model_validate({"passed": True, "summary": "all green"})
    assert passed.failure_class is None and passed.report_ref is None
    with pytest.raises(ValidationError):
        GateResultPayload.model_validate({"summary": "no verdict"})


def test_decision_needed_payload() -> None:
    p = DecisionNeededPayload.model_validate({"decision_id": "d1", "kind": "clarify", "question": "?"})
    assert p.question == "?"
