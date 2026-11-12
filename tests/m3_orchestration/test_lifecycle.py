# FILE: tests/m3_orchestration/test_lifecycle.py
# ROLE: Tests that prove src/asf/m3_orchestration/lifecycle.py meets its DONE WHEN conditions.
# ARCH REF: M3; p06 Task node lifecycle; A-3; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/lifecycle.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/lifecycle.py: transition, ALLOWED_TRANSITIONS, MAX_ATTEMPTS (unit under test)
#   - imports from src/asf/contracts/errors.py: StateConflict (used here)
#   - imports from src/asf/contracts/tasks.py: TaskNode, TaskState (used here)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/test_lifecycle.py` on Windows and Linux once src/asf/m3_orchestration/lifecycle.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/test_lifecycle.py` and `uv run mypy tests/m3_orchestration/test_lifecycle.py` are clean.

import pytest

from asf.contracts.errors import StateConflict
from asf.contracts.tasks import TaskNode, TaskState
from asf.m3_orchestration.lifecycle import ALLOWED_TRANSITIONS, MAX_ATTEMPTS, transition

S = TaskState
FINAL = {S.VERIFIED, S.INTEGRATED, S.CANCELLED, S.ABANDONED}


def _node(state: TaskState = S.PROPOSED, **counters: int) -> TaskNode:
    return TaskNode.model_validate(
        {"id": "t1", "run_id": "r1", "kind": "leaf", "goal": "g", "idempotency_key": "k", "state": state, "counters": counters}
    )


def _walk(node: TaskNode, *steps: tuple[TaskState, str]) -> TaskNode:
    for to, reason in steps:
        node = transition(node, to, reason)
    return node


def test_every_state_has_an_entry() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(TaskState)


def test_final_states_have_no_exits() -> None:
    for state in FINAL:
        assert ALLOWED_TRANSITIONS[state] == frozenset()


def test_every_non_final_state_can_be_suspended_and_cancelled() -> None:
    for state in set(TaskState) - FINAL:
        assert {S.CANCELLED} <= ALLOWED_TRANSITIONS[state]
        if state is not S.SUSPENDED:
            assert S.SUSPENDED in ALLOWED_TRANSITIONS[state]


def test_the_leaf_happy_path() -> None:
    node = _walk(
        _node(), (S.SIZING, "popped"), (S.LEAF_CERTIFIED, "fits"), (S.BLOCKED, "deps pending"), (S.READY, "deps verified"),
        (S.RUNNING, "lease"), (S.VERIFYING, "change set"), (S.VERIFIED, "gates pass"),
    )
    assert node.state is S.VERIFIED and node.counters.attempts == 1


def test_the_composite_happy_path() -> None:
    node = _walk(
        _node(), (S.SIZING, "popped"), (S.SPLITTING, "too big"), (S.DECOMPOSED, "committed"), (S.CHILDREN_DONE, "all children done"),
        (S.INTEGRATING, "start"), (S.REPAIRING, "failed"), (S.INTEGRATING, "patched"), (S.INTEGRATED, "green"),
    )
    assert node.state is S.INTEGRATED and node.counters.split_attempts == 1


def test_the_original_node_is_never_mutated() -> None:
    node = _node()
    updated = transition(node, S.SIZING, "popped")
    assert node.state is S.PROPOSED and updated.state is S.SIZING and updated is not node


@pytest.mark.parametrize(
    ("src", "dst"),
    [(S.PROPOSED, S.READY), (S.READY, S.VERIFIED), (S.VERIFIED, S.READY), (S.INTEGRATED, S.SIZING), (S.CANCELLED, S.PROPOSED), (S.SIZING, S.RUNNING)],
)
def test_illegal_edges_raise_state_conflict(src: TaskState, dst: TaskState) -> None:
    with pytest.raises(StateConflict):
        transition(_node(src), dst, "nope")


def test_pause_records_the_prior_state_and_resume_restores_exactly_it() -> None:
    running = _node(S.RUNNING)
    paused = transition(running, S.SUSPENDED, "pause")
    assert paused.prior_state is S.RUNNING
    with pytest.raises(StateConflict):
        transition(paused, S.READY, "wrong place")
    resumed = transition(paused, S.RUNNING, "resume")
    assert resumed.state is S.RUNNING and resumed.prior_state is None


def test_a_suspended_node_can_still_be_cancelled() -> None:
    assert transition(transition(_node(S.READY), S.SUSPENDED, "pause"), S.CANCELLED, "abort").state is S.CANCELLED


def test_attempts_are_charged_on_running_and_bounded() -> None:
    node = _node(S.READY, attempts=MAX_ATTEMPTS)
    with pytest.raises(StateConflict):
        transition(node, S.RUNNING, "lease")
    assert transition(_node(S.READY, attempts=MAX_ATTEMPTS - 1), S.RUNNING, "lease").counters.attempts == MAX_ATTEMPTS


def test_a_failed_attempt_returns_to_ready_only_while_attempts_remain() -> None:
    assert transition(_node(S.FAILED_ATTEMPT, attempts=2), S.READY, "retry").state is S.READY
    with pytest.raises(StateConflict):
        transition(_node(S.FAILED_ATTEMPT, attempts=3), S.READY, "retry")
    assert transition(_node(S.FAILED_ATTEMPT, attempts=3), S.ESCALATED, "exhausted").state is S.ESCALATED


def test_a_lost_run_goes_back_to_ready_without_charging_an_attempt() -> None:
    node = transition(_node(S.RUNNING, attempts=2), S.READY, "interrupted: crash")
    assert node.counters.attempts == 1 and node.counters.interruptions == 1
    infra = transition(_node(S.RUNNING, attempts=1), S.READY, "infra: lease lost")
    assert infra.counters.attempts == 0 and infra.counters.interruptions == 0


def test_running_to_ready_needs_a_loss_reason_and_is_capped() -> None:
    with pytest.raises(StateConflict):
        transition(_node(S.RUNNING), S.READY, "felt like it")
    with pytest.raises(StateConflict):
        transition(_node(S.RUNNING, interruptions=3), S.READY, "interrupted again")
    assert transition(_node(S.RUNNING, interruptions=3), S.ESCALATED, "too many interruptions").state is S.ESCALATED


def test_split_attempts_and_the_single_resplit_are_bounded() -> None:
    assert transition(_node(S.SIZING, split_attempts=2), S.SPLITTING, "tier escalation").counters.split_attempts == 3
    with pytest.raises(StateConflict):
        transition(_node(S.SIZING, split_attempts=3), S.SPLITTING, "again")
    resplit = transition(_node(S.FAILED_ATTEMPT), S.SPLITTING, "SPEC_TOO_LARGE")
    assert resplit.counters.resplits == 1 and resplit.counters.split_attempts == 0
    with pytest.raises(StateConflict):
        transition(_node(S.VERIFYING, resplits=1), S.SPLITTING, "again")


def test_an_escalated_node_can_be_replanned_or_abandoned() -> None:
    assert transition(_node(S.ESCALATED), S.SIZING, "re-planned").state is S.SIZING
    assert transition(_node(S.ESCALATED), S.ABANDONED, "user abandons").state is S.ABANDONED
