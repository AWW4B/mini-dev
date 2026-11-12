# FILE: tests/contracts/test_decisions.py
# ROLE: Tests that prove src/asf/contracts/decisions.py meets its DONE WHEN conditions.
# ARCH REF: p10 Decision Broker; p02 Decision Inbox; IF-03; IF-04; D-10; D-21; D-22; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/decisions.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/decisions.py: DecisionKind, DecisionRequest, DecisionResolved, NEVER_AUTO_APPROVED (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_decisions.py` on Windows and Linux once src/asf/contracts/decisions.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_decisions.py` and `uv run mypy tests/contracts/test_decisions.py` are clean.


from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from asf.contracts.decisions import NEVER_AUTO_APPROVED, DecisionKind, DecisionRequest, DecisionResolved


def _request() -> dict[str, Any]:
    return {
        "decision_id": "d1",
        "run_id": "r1",
        "kind": "clarify",
        "requester": "asf.m2_request.pipeline",
        "question": "Which database?",
        "options": ["sqlite", "postgres"],
        "default_on_timeout": "sqlite",
    }


def test_never_auto_approved_is_exactly_the_unsafe_kinds() -> None:
    assert isinstance(NEVER_AUTO_APPROVED, frozenset)
    assert frozenset({
        DecisionKind.BREAKING_CONTRACT,
        DecisionKind.TOOL_PERMISSION,
        DecisionKind.BUDGET_RAISE,
        DecisionKind.UNSANDBOXED_EXECUTION,
        DecisionKind.DEPENDENCY_INSTALL,
        DecisionKind.NO_WHEEL_EXCEPTION,
    }) == NEVER_AUTO_APPROVED


@pytest.mark.parametrize("kind", [DecisionKind.CLARIFY, DecisionKind.APPROVE_PLAN, DecisionKind.ESCALATION, DecisionKind.MANUAL_SPLIT])
def test_routine_kinds_may_be_defaulted(kind: DecisionKind) -> None:
    assert kind not in NEVER_AUTO_APPROVED


def test_kind_values_are_lowercase_snake_case_and_unique() -> None:
    values = [k.value for k in DecisionKind]
    assert len(values) == len(set(values)) == 11
    assert all(v == v.lower() and " " not in v for v in values)


def test_request_defaults() -> None:
    req = DecisionRequest.model_validate(_request())
    assert req.task_id is None
    assert req.deadline is None
    assert req.evidence_refs == []


def test_default_on_timeout_must_be_stated_but_may_be_none() -> None:
    data = _request()
    del data["default_on_timeout"]
    with pytest.raises(ValidationError):
        DecisionRequest.model_validate(data)
    assert DecisionRequest.model_validate({**_request(), "default_on_timeout": None}).default_on_timeout is None


def test_request_parses_iso_deadline_and_round_trips() -> None:
    req = DecisionRequest.model_validate({**_request(), "deadline": "2026-11-12T10:00:00+00:00"})
    assert req.deadline == datetime(2026, 11, 12, 10, 0, tzinfo=UTC)
    assert DecisionRequest.model_validate_json(req.model_dump_json()) == req


def test_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DecisionRequest.model_validate({**_request(), "kind": "yolo"})


def test_resolved_defaults_to_a_human_answer() -> None:
    res = DecisionResolved.model_validate(
        {"decision_id": "d1", "choice": "sqlite", "answered_by": "user", "answered_at": "2026-11-12T10:00:00+00:00"}
    )
    assert res.applied_default is False
    assert res.text is None


def test_resolved_requires_answered_at() -> None:
    with pytest.raises(ValidationError):
        DecisionResolved.model_validate({"decision_id": "d1", "choice": "x", "answered_by": "user"})
