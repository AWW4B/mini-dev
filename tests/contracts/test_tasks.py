# FILE: tests/contracts/test_tasks.py
# ROLE: Tests that prove src/asf/contracts/tasks.py meets its DONE WHEN conditions.
# ARCH REF: p05; p06 states; p15 TaskNode, LeafTaskSpec, AttemptRecord; IF-09 ReadyTask; A-2, A-3; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/tasks.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tasks.py: NodeKind, TaskState, NodeCounters, TaskNode, StepBudget, LeafTaskSpec, AttemptRecord (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_tasks.py` on Windows and Linux once src/asf/contracts/tasks.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_tasks.py` and `uv run mypy tests/contracts/test_tasks.py` are clean.


from typing import Any

import pytest
from pydantic import ValidationError

from asf.contracts.tasks import AttemptRecord, LeafTaskSpec, NodeCounters, NodeKind, StepBudget, TaskNode, TaskState


def _node(**over: Any) -> dict[str, Any]:
    return {"id": "t1", "run_id": "r1", "kind": "leaf", "goal": "write blobs.py", "idempotency_key": "k1", **over}


def _capsule(lines: int = 3) -> dict[str, Any]:
    return {"module_id": "blobs", "version": "1.0.0", "operation": "put", "lines": ["l"] * lines}


def _leaf(**over: Any) -> dict[str, Any]:
    return {
        "task_id": "t1", "goal": "g", "acceptance_test_refs": ["tests/test_x.py"], "capsules": [_capsule()],
        "allowed_files": ["src/x.py"], "context_budget_tokens": 4000, "base_commit": "abc123", "parent_branch": "main", **over,
    }


def test_node_kinds() -> None:
    assert {k.value for k in NodeKind} == {"composite", "leaf", "integration", "repair", "shared_types"}


def test_task_state_machine_has_every_documented_state() -> None:
    assert len(TaskState) == 21
    for name in ("PROPOSED", "READY", "RUNNING", "VERIFIED", "INTEGRATED", "ESCALATED", "CANCELLED", "ABANDONED"):
        assert TaskState[name].value == name


def test_counters_start_at_zero() -> None:
    c = NodeCounters()
    assert (c.split_attempts, c.resplits, c.attempts, c.interruptions, c.repair_rounds) == (0, 0, 0, 0, 0)


def test_node_defaults() -> None:
    node = TaskNode.model_validate(_node())
    assert node.state is TaskState.PROPOSED
    assert node.prior_state is None and node.parent_id is None and node.size_estimate is None
    assert node.depth == 0 and node.priority == 0
    assert node.deps == [] and node.allowed_files == [] and node.acceptance_refs == [] and node.contract_refs == []


def test_node_counters_and_lists_are_per_instance() -> None:
    a = TaskNode.model_validate(_node())
    b = TaskNode.model_validate(_node())
    a.counters.attempts += 1
    a.allowed_files.append("src/x.py")
    assert b.counters.attempts == 0
    assert b.allowed_files == []


@pytest.mark.parametrize("missing", ["id", "run_id", "kind", "goal", "idempotency_key"])
def test_node_required_fields(missing: str) -> None:
    data = _node()
    del data[missing]
    with pytest.raises(ValidationError):
        TaskNode.model_validate(data)


def test_node_rejects_unknown_state() -> None:
    with pytest.raises(ValidationError):
        TaskNode.model_validate(_node(state="LOST"))


def test_node_json_round_trip_with_nested_counters() -> None:
    node = TaskNode.model_validate(_node(state="RUNNING", prior_state="READY", counters={"attempts": 2}, deps=["t0"]))
    again = TaskNode.model_validate_json(node.model_dump_json())
    assert again == node
    assert again.counters.attempts == 2


def test_step_budget_defaults() -> None:
    sb = StepBudget()
    assert (sb.max_turns, sb.max_output_tokens_per_turn, sb.wall_clock_s) == (12, 2048, 900)


def test_leaf_spec_defaults() -> None:
    leaf = LeafTaskSpec.model_validate(_leaf())
    assert leaf.model_role == "T2"
    assert leaf.max_attempts == 3
    assert leaf.read_only_files == []
    assert leaf.step_budget.max_turns == 12


def test_leaf_spec_capsules_keep_their_line_limit() -> None:
    assert len(LeafTaskSpec.model_validate(_leaf(capsules=[_capsule(5)])).capsules[0].lines) == 5
    with pytest.raises(ValidationError):
        LeafTaskSpec.model_validate(_leaf(capsules=[_capsule(2)]))
    with pytest.raises(ValidationError):
        LeafTaskSpec.model_validate(_leaf(capsules=[_capsule(6)]))


def test_leaf_spec_requires_base_commit_and_branch() -> None:
    for missing in ("base_commit", "parent_branch", "allowed_files", "context_budget_tokens"):
        data = _leaf()
        del data[missing]
        with pytest.raises(ValidationError):
            LeafTaskSpec.model_validate(data)


def test_attempt_record_defaults_flag_measured_usage() -> None:
    rec = AttemptRecord.model_validate(
        {"attempt_id": "a1", "task_id": "t1", "attempt_no": 1, "model": "m", "tier": "T2", "strategy": "tool_loop"}
    )
    assert rec.measured is True
    assert (rec.tokens_in, rec.tokens_out, rec.inference_s) == (0, 0, 0.0)
    assert rec.lease_id is None and rec.diff_ref is None and rec.failure_class is None
