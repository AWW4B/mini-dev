# FILE: tests/m3_orchestration/test_escalation.py
# ROLE: Tests that prove src/asf/m3_orchestration/escalation.py meets its DONE WHEN conditions.
# ARCH REF: M3; p04 Escalation & Recovery; IF-10; A-3; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/escalation.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/escalation.py: handle_escalation (unit under test)
#   - imports from src/asf/contracts/outcomes.py: TaskOutcome (used here)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/test_escalation.py` on Windows and Linux once src/asf/m3_orchestration/escalation.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/test_escalation.py` and `uv run mypy tests/m3_orchestration/test_escalation.py` are clean.

from types import SimpleNamespace
from typing import Any

import pytest

from asf.contracts.outcomes import TaskOutcome
from asf.m3_orchestration.escalation import handle_escalation


class _Broker:
    def __init__(self) -> None:
        self.requests: list[Any] = []
        self.resolved_answers: dict[str, Any] = {}

    def request(self, req: Any) -> None:
        self.requests.append(req)


def _outcome(failure: str, task_id: str = "t1") -> TaskOutcome:
    return TaskOutcome.model_validate({"task_id": task_id, "failure_class": failure, "evidence_ref": "sha256:ev", "attempts": 3})


@pytest.mark.parametrize("failure", ["SPEC_TOO_LARGE", "CONTEXT_OVERFLOW"])
def test_size_problems_are_resplit_once(failure: str) -> None:
    broker = _Broker()
    assert handle_escalation(_outcome(failure), broker=broker) == "resplit"  # type: ignore[arg-type]
    assert broker.requests == []


@pytest.mark.parametrize("failure", ["CONTRACT_MISMATCH", "CONTRACT_GAP", "ESCALATED", "LOCAL_BUG"])
def test_contract_and_worker_failures_replan_while_budget_and_rounds_remain(failure: str) -> None:
    assert handle_escalation(_outcome(failure), replans_done=1) == "replan"


def test_a_second_size_failure_asks_for_a_manual_split() -> None:
    broker = _Broker()
    assert handle_escalation(_outcome("SPEC_TOO_LARGE"), broker=broker, resplits_done=1) == "ask_user"  # type: ignore[arg-type]
    (req,) = broker.requests
    assert req.kind.value == "manual_split" and req.default_on_timeout is None
    assert "accept_larger_leaf" in req.options and req.evidence_refs == ["sha256:ev"]


def test_exhausted_replans_ask_the_user() -> None:
    broker = _Broker()
    assert handle_escalation(_outcome("CONTRACT_MISMATCH"), broker=broker, replans_done=2) == "ask_user"  # type: ignore[arg-type]
    assert broker.requests[0].kind.value == "escalation"


def test_an_exhausted_budget_asks_for_a_budget_raise_first() -> None:
    broker = _Broker()
    assert handle_escalation(_outcome("LOCAL_BUG"), broker=broker, budget_left=False) == "ask_user"  # type: ignore[arg-type]
    assert broker.requests[0].kind.value == "budget_raise"
    assert broker.requests[0].options == ["raise_budget", "abort_run"]


def test_environment_failures_are_for_a_person() -> None:
    broker = _Broker()
    assert handle_escalation(_outcome("ENV_INFRA"), broker=broker) == "ask_user"  # type: ignore[arg-type]
    assert broker.requests[0].kind.value == "escalation"


def test_the_question_is_asked_once_and_the_answer_is_honoured_later() -> None:
    broker = _Broker()
    outcome = _outcome("ENV_INFRA")
    handle_escalation(outcome, broker=broker)  # type: ignore[arg-type]
    decision_id = broker.requests[0].decision_id
    broker.resolved_answers[decision_id] = SimpleNamespace(choice="abandon_subtree")
    assert handle_escalation(outcome, broker=broker) == "abandon"  # type: ignore[arg-type]
    assert len(broker.requests) == 1
    broker.resolved_answers[decision_id] = SimpleNamespace(choice="replan")
    assert handle_escalation(outcome, broker=broker) == "replan"  # type: ignore[arg-type]


def test_without_a_broker_the_user_question_is_still_reported_as_ask_user() -> None:
    assert handle_escalation(_outcome("ENV_INFRA")) == "ask_user"


def test_the_run_id_comes_from_the_store_when_it_has_the_task() -> None:
    broker = _Broker()
    store = SimpleNamespace(get_task=lambda task_id: SimpleNamespace(run_id="run-42"))
    handle_escalation(_outcome("ENV_INFRA"), broker=broker, store=store)  # type: ignore[arg-type]
    assert broker.requests[0].run_id == "run-42"
