# FILE: tests/contracts/test_outcomes.py
# ROLE: Tests that prove src/asf/contracts/outcomes.py meets its DONE WHEN conditions.
# ARCH REF: p05; p07; p08; p16; IF-07a; IF-10; IF-10b; IF-10c; IF-21; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/outcomes.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/outcomes.py: FailureClass, TaskOutcome, ChangeSet, Requeue, ApprovedPlan, DecompositionReport, RootIntegrated (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_outcomes.py` on Windows and Linux once src/asf/contracts/outcomes.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_outcomes.py` and `uv run mypy tests/contracts/test_outcomes.py` are clean.


from typing import Any

import pytest
from pydantic import ValidationError

from asf.contracts.outcomes import ApprovedPlan, ChangeSet, DecompositionReport, FailureClass, Requeue, RootIntegrated, TaskOutcome


def _node(task_id: str = "t_root") -> dict[str, Any]:
    return {"id": task_id, "run_id": "r1", "kind": "composite", "goal": "build it", "idempotency_key": "k-" + task_id}


def test_failure_classes_are_the_nine_documented_values() -> None:
    assert {f.value for f in FailureClass} == {
        "LOCAL_BUG", "FLAKY", "ENV_INFRA", "CONTRACT_MISMATCH", "SPEC_TOO_LARGE",
        "CONTEXT_OVERFLOW", "CONTRACT_GAP", "POLICY_VIOLATION", "ESCALATED",
    }


def test_task_outcome() -> None:
    out = TaskOutcome.model_validate({"task_id": "t1", "failure_class": "FLAKY", "attempts": 2})
    assert out.failure_class is FailureClass.FLAKY
    assert out.evidence_ref is None
    with pytest.raises(ValidationError):
        TaskOutcome.model_validate({"task_id": "t1", "failure_class": "BROKEN", "attempts": 2})


def test_change_set_requires_diff_and_touched_files() -> None:
    data = {
        "task_id": "t1", "attempt_no": 1, "diff_ref": "sha256:ab", "worktree_path": "wt/t1",
        "files_touched": ["a.py"], "self_report": "done",
    }
    assert ChangeSet.model_validate(data).files_touched == ["a.py"]
    del data["diff_ref"]
    with pytest.raises(ValidationError):
        ChangeSet.model_validate(data)


def test_requeue() -> None:
    rq = Requeue.model_validate({"task_id": "t1", "failure_class": "LOCAL_BUG", "evidence_ref": "sha256:cd"})
    assert rq.failure_class is FailureClass.LOCAL_BUG
    with pytest.raises(ValidationError):
        Requeue.model_validate({"task_id": "t1", "failure_class": "LOCAL_BUG"})


def test_approved_plan_nests_task_nodes_and_defaults_shared_types() -> None:
    plan = ApprovedPlan.model_validate({"run_id": "r1", "root": _node(), "module_nodes": [_node("t_a")], "contract_ids": ["c1"]})
    assert plan.root.goal == "build it"
    assert plan.module_nodes[0].id == "t_a"
    assert plan.shared_type_nodes == []
    assert ApprovedPlan.model_validate_json(plan.model_dump_json()) == plan


def test_approved_plan_rejects_an_invalid_nested_node() -> None:
    bad = _node()
    del bad["goal"]
    with pytest.raises(ValidationError):
        ApprovedPlan.model_validate({"run_id": "r1", "root": bad, "module_nodes": [], "contract_ids": []})


def test_decomposition_report_and_root_integrated() -> None:
    rep = DecompositionReport.model_validate({"run_id": "r1", "complete": False, "untraced_requirements": ["REQ-1"], "suspended_nodes": ["t3"]})
    assert rep.complete is False and rep.untraced_requirements == ["REQ-1"]
    done = RootIntegrated.model_validate({"run_id": "r1", "root_task": "t_root", "report_ref": "sha256:ee"})
    assert done.root_task == "t_root"
    with pytest.raises(ValidationError):
        RootIntegrated.model_validate({"run_id": "r1", "root_task": "t_root"})
