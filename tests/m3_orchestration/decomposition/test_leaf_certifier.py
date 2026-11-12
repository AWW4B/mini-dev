# FILE: tests/m3_orchestration/decomposition/test_leaf_certifier.py
# ROLE: Tests that prove src/asf/m3_orchestration/decomposition/leaf_certifier.py meets its DONE WHEN conditions.
# ARCH REF: M3; p05 leaf certification; IF-09 ReadyTask; A-1; A-4; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/decomposition/leaf_certifier.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/decomposition/leaf_certifier.py: certify_leaf (unit under test)
#   - imports from src/asf/contracts/tasks.py: TaskNode (node fixtures)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/decomposition/test_leaf_certifier.py` on Windows and Linux once src/asf/m3_orchestration/decomposition/leaf_certifier.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/decomposition/test_leaf_certifier.py` and `uv run mypy tests/m3_orchestration/decomposition/test_leaf_certifier.py` are clean.

from types import SimpleNamespace
from typing import Any

import pytest

from asf.contracts.tasks import TaskNode
from asf.m3_orchestration.decomposition.leaf_certifier import certify_leaf


def _node(**over: Any) -> TaskNode:
    base = {
        "id": "t1", "run_id": "r1", "kind": "composite", "goal": "implement refunds", "idempotency_key": "k",
        "allowed_files": ["src/refund.py"], "acceptance_refs": ["tests/test_refund.py::test_refund"], "contract_refs": ["ledger@1.0.0", "money"],
    }
    return TaskNode.model_validate({**base, **over})


class _Registry:
    def __init__(self) -> None:
        self.queries: list[Any] = []

    def query(self, q: Any) -> list[Any]:
        self.queries.append(q)
        return [{"module_id": m, "version": q.pinned_versions.get(m, "latest"), "operation": "op", "lines": ["a", "b", "c"]} for m in q.module_ids]


def test_a_leaf_spec_is_built_with_pinned_capsules_files_and_commit() -> None:
    registry = _Registry()
    spec = certify_leaf(_node(), "abc123", "task/parent", registry=registry, read_only_files=["src/money.py"])  # type: ignore[arg-type]
    assert spec.task_id == "t1" and spec.goal == "implement refunds"
    assert spec.acceptance_test_refs == ["tests/test_refund.py::test_refund"]
    assert spec.allowed_files == ["src/refund.py"] and spec.read_only_files == ["src/money.py"]
    assert spec.base_commit == "abc123" and spec.parent_branch == "task/parent"
    assert spec.model_role == "T2" and spec.max_attempts == 3 and spec.context_budget_tokens == 8000


def test_capsules_are_pinned_to_the_versions_named_in_the_contract_refs() -> None:
    registry = _Registry()
    certify_leaf(_node(), "c", "b", registry=registry)  # type: ignore[arg-type]
    (query,) = registry.queries
    assert query.module_ids == ["ledger", "money"] and query.pinned_versions == {"ledger": "1.0.0"}


def test_no_registry_or_no_contracts_means_no_capsules() -> None:
    assert certify_leaf(_node(), "c", "b").capsules == []
    assert certify_leaf(_node(contract_refs=[]), "c", "b", registry=_Registry()).capsules == []  # type: ignore[arg-type]


def test_criteria_that_are_not_tests_are_authored_by_the_planner_tier() -> None:
    node = _node(acceptance_refs=["refund returns a receipt"])
    written: list[TaskNode] = []

    def authoring(n: TaskNode) -> list[str]:
        written.append(n)
        return ["tests/test_refund.py"]

    spec = certify_leaf(node, "c", "b", authoring=authoring)
    assert spec.acceptance_test_refs == ["tests/test_refund.py"] and written == [node]


def test_existing_test_refs_are_not_rewritten() -> None:
    def authoring(n: TaskNode) -> list[str]:
        raise AssertionError("tests already exist")

    assert certify_leaf(_node(), "c", "b", authoring=authoring).acceptance_test_refs == ["tests/test_refund.py::test_refund"]


def test_a_leaf_never_goes_out_without_tests() -> None:
    with pytest.raises(ValueError, match="no acceptance tests"):
        certify_leaf(_node(acceptance_refs=["plain text"]), "c", "b")
    with pytest.raises(ValueError, match="produced no tests"):
        certify_leaf(_node(acceptance_refs=[]), "c", "b", authoring=lambda n: [])


def test_a_node_without_files_cannot_be_a_leaf() -> None:
    with pytest.raises(ValueError, match="owns no files"):
        certify_leaf(_node(allowed_files=[]), "c", "b")


def test_the_context_budget_is_configurable() -> None:
    assert certify_leaf(_node(), "c", "b", context_budget_tokens=4096).context_budget_tokens == 4096
    _ = SimpleNamespace
