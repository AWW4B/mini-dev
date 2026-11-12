# FILE: tests/m3_orchestration/decomposition/test_split_validator.py
# ROLE: Tests that prove src/asf/m3_orchestration/decomposition/split_validator.py meets its DONE WHEN conditions.
# ARCH REF: M3; p05 split validation; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/decomposition/split_validator.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/decomposition/split_validator.py: validate_split (unit under test)
#   - imports from src/asf/contracts/tasks.py: TaskNode (node fixtures)
#   - imports from src/asf/m3_orchestration/decomposition/splitter.py: SplitProposal (the input of validate_split)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/decomposition/test_split_validator.py` on Windows and Linux once src/asf/m3_orchestration/decomposition/split_validator.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/decomposition/test_split_validator.py` and `uv run mypy tests/m3_orchestration/decomposition/test_split_validator.py` are clean.

from typing import Any

from asf.contracts.tasks import TaskNode
from asf.m3_orchestration.decomposition.split_validator import validate_split
from asf.m3_orchestration.decomposition.splitter import SplitProposal


def _node(node_id: str, **over: Any) -> TaskNode:
    base = {"id": node_id, "run_id": "r1", "kind": "composite", "goal": f"goal {node_id}", "idempotency_key": f"key-{node_id}"}
    return TaskNode.model_validate({**base, **over})


PARENT = _node("p", acceptance_refs=["a1", "a2"], allowed_files=["src/a.py", "src/b.py"], size_estimate=1000)


def _good() -> list[TaskNode]:
    return [
        _node("p.1", acceptance_refs=["a1"], allowed_files=["src/a.py"], size_estimate=500),
        _node("p.2", acceptance_refs=["a2"], allowed_files=["src/b.py"], deps=["p.1"], size_estimate=600),
    ]


def _proposal(children: list[TaskNode], parent_id: str = "p") -> SplitProposal:
    return SplitProposal(parent_id=parent_id, children=children, new_contract_ids=[], rationale="r")


def test_a_good_split_has_no_problems() -> None:
    assert validate_split(PARENT, _proposal(_good())) == []


def test_the_proposal_must_be_for_this_parent() -> None:
    assert any("not for 'p'" in p for p in validate_split(PARENT, _proposal(_good(), parent_id="other")))


def test_the_number_of_children_is_bounded() -> None:
    assert any("needs 2 to 8 children" in p for p in validate_split(PARENT, _proposal(_good()[:1])))
    many = [_node(f"p.{i}", acceptance_refs=["a1", "a2"], allowed_files=[f"src/f{i}.py"]) for i in range(9)]
    assert any("needs 2 to 8 children" in p for p in validate_split(_node("p", acceptance_refs=["a1", "a2"]), _proposal(many)))


def test_every_parent_criterion_must_be_covered() -> None:
    children = _good()
    children[1] = children[1].model_copy(update={"acceptance_refs": []})
    assert validate_split(PARENT, _proposal(children)) == ["acceptance criterion 'a2' of the parent is not covered by any child"]


def test_dependency_cycles_are_found() -> None:
    children = _good()
    children[0] = children[0].model_copy(update={"deps": ["p.2"]})
    assert any("cycle among: p.1, p.2" in p for p in validate_split(PARENT, _proposal(children)))


def test_a_child_depending_on_itself_is_reported() -> None:
    children = _good()
    children[0] = children[0].model_copy(update={"deps": ["p.1"]})
    assert any("depends on itself" in p for p in validate_split(PARENT, _proposal(children)))


def test_external_dependencies_are_not_cycles() -> None:
    children = _good()
    children[0] = children[0].model_copy(update={"deps": ["some-other-module"]})
    assert validate_split(PARENT, _proposal(children)) == []


def test_files_must_be_disjoint_non_empty_and_inside_the_parent() -> None:
    shared = _good()
    shared[1] = shared[1].model_copy(update={"allowed_files": ["src/a.py"]})
    assert any("owned by both" in p for p in validate_split(PARENT, _proposal(shared)))
    none = _good()
    none[0] = none[0].model_copy(update={"allowed_files": []})
    assert any("owns no files" in p for p in validate_split(PARENT, _proposal(none)))
    outside = _good()
    outside[0] = outside[0].model_copy(update={"allowed_files": ["src/elsewhere.py"]})
    assert any("outside the parent's files" in p for p in validate_split(PARENT, _proposal(outside)))


def test_a_parent_without_files_does_not_restrict_the_children() -> None:
    parent = _node("p", acceptance_refs=["a1", "a2"])
    assert validate_split(parent, _proposal(_good())) == []


def test_duplicate_children_and_ids_are_reported() -> None:
    twins = _good()
    twins[1] = twins[1].model_copy(update={"idempotency_key": twins[0].idempotency_key})
    assert any("duplicates" in p for p in validate_split(PARENT, _proposal(twins)))
    same_id = _good()
    same_id[1] = same_id[1].model_copy(update={"id": "p.1"})
    assert any("appears twice" in p for p in validate_split(PARENT, _proposal(same_id)))


def test_the_progress_rule_requires_children_to_be_smaller() -> None:
    children = _good()
    children[1] = children[1].model_copy(update={"size_estimate": 900})  # 900 > 0.8 * 1000
    assert any("not smaller enough" in p for p in validate_split(PARENT, _proposal(children)))
    assert validate_split(PARENT, _proposal(children), alpha=0.95) == []


def test_sizes_that_are_not_known_are_not_checked() -> None:
    parent = PARENT.model_copy(update={"size_estimate": None})
    children = [c.model_copy(update={"size_estimate": 99999}) for c in _good()]
    assert validate_split(parent, _proposal(children)) == []
