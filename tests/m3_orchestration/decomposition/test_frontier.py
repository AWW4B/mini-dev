# FILE: tests/m3_orchestration/decomposition/test_frontier.py
# ROLE: Tests that prove src/asf/m3_orchestration/decomposition/frontier.py meets its DONE WHEN conditions.
# ARCH REF: M3; p05 persisted frontier; D-06 (batched loop, recursion_limit never the terminator); D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/decomposition/frontier.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/decomposition/frontier.py: Frontier (unit under test)
#   - imports from src/asf/contracts/tasks.py: TaskNode (node fixtures)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (persisted frontier)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/decomposition/test_frontier.py` on Windows and Linux once src/asf/m3_orchestration/decomposition/frontier.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/decomposition/test_frontier.py` and `uv run mypy tests/m3_orchestration/decomposition/test_frontier.py` are clean.

from pathlib import Path
from typing import Any

import pytest

from asf.contracts.tasks import TaskNode
from asf.m3_orchestration.decomposition.frontier import Frontier
from asf.m5_shared.state_store.store import StateStore


def _node(node_id: str, **over: Any) -> TaskNode:
    base = {"id": node_id, "run_id": "r1", "kind": "composite", "goal": f"goal {node_id}", "idempotency_key": f"k-{node_id}"}
    return TaskNode.model_validate({**base, **over})


def _ids(nodes: list[TaskNode]) -> list[str]:
    return [str(n.id) for n in nodes]


def test_pop_returns_the_highest_priority_then_shallowest_then_oldest() -> None:
    f = Frontier("r1")
    f.push([_node("old", priority=1), _node("deep", priority=5, depth=3), _node("shallow", priority=5, depth=1), _node("new", priority=1)])
    assert _ids(f.pop_batch(10)) == ["shallow", "deep", "old", "new"]


def test_batches_are_bounded_and_popped_nodes_are_not_popped_twice() -> None:
    f = Frontier("r1")
    f.push([_node(f"n{i}") for i in range(5)])
    assert _ids(f.pop_batch(2)) == ["n0", "n1"]
    assert _ids(f.pop_batch(2)) == ["n2", "n3"]
    assert _ids(f.pop_batch(10)) == ["n4"]
    assert f.pop_batch(10) == [] and f.pop_batch(0) == []


def test_only_proposed_nodes_may_enter_and_duplicates_are_ignored() -> None:
    f = Frontier("r1")
    with pytest.raises(ValueError, match="PROPOSED"):
        f.push([_node("x", state="READY")])
    f.push([_node("a")])
    f.push([_node("a")])
    assert len(f) == 1


def test_length_counts_waiting_and_in_flight_nodes() -> None:
    f = Frontier("r1")
    f.push([_node("a"), _node("b")])
    (a,) = f.pop_batch(1)
    assert len(f) == 2  # still being worked on
    f.update(a.model_copy(update={"state": "SIZING"}))
    assert len(f) == 1


def test_a_node_that_is_proposed_again_re_enters() -> None:
    f = Frontier("r1")
    f.push([_node("a")])
    (a,) = f.pop_batch(1)
    f.update(a)
    assert _ids(f.pop_batch(1)) == ["a"]


def test_parked_nodes_wait_until_all_their_dependencies_are_verified() -> None:
    f = Frontier("r1")
    f.push([_node("child", deps=["d1", "d2"])])
    f.pop_batch(1)
    f.park("child")
    assert f.deferred_ids() == ["child"] and len(f) == 0
    assert f.wake_dependents("d1") == 0
    assert f.wake_dependents("d2") == 1
    assert f.deferred_ids() == [] and _ids(f.pop_batch(1)) == ["child"]
    assert f.is_verified("d1")


def test_parking_an_unknown_node_is_an_error() -> None:
    with pytest.raises(KeyError):
        Frontier("r1").park("ghost")


def test_a_verification_that_arrives_before_the_park_is_remembered() -> None:
    f = Frontier("r1")
    f.wake_dependents("d1")
    f.push([_node("child", deps=["d1"])])
    f.pop_batch(1)
    f.park("child")
    assert f.wake_dependents("other") == 1  # d1 was already verified


def test_state_is_written_through_and_a_new_frontier_reloads_it(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "state.db")
    f = Frontier("r1", store)
    f.push([_node("a", priority=2), _node("b"), _node("c", deps=["x"])])
    popped = f.pop_batch(3)
    f.park("c")
    f.update(popped[0].model_copy(update={"state": "SIZING"}))  # a is being sized when the process dies

    again = Frontier("r1", store)
    assert again.deferred_ids() == ["c"]
    assert sorted(_ids(again.pop_batch(10))) == ["a", "b"]  # a (interrupted SIZING) and b come back as PROPOSED
    states = {r["task_id"]: r["state"] for r in store.conn.execute("SELECT task_id, state FROM tasks")}
    assert states == {"a": "SIZING", "b": "PROPOSED", "c": "DEFERRED"}


def test_other_runs_are_not_loaded(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "state.db")
    Frontier("r1", store).push([_node("mine")])
    Frontier("r2", store).push([_node("theirs", run_id="r2")])
    assert _ids(Frontier("r2", store).pop_batch(10)) == ["theirs"]
