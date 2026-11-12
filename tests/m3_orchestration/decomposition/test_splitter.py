# FILE: tests/m3_orchestration/decomposition/test_splitter.py
# ROLE: Tests that prove src/asf/m3_orchestration/decomposition/splitter.py meets its DONE WHEN conditions.
# ARCH REF: M3; p05 split proposal; A-1; A-2; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/decomposition/splitter.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/decomposition/splitter.py: SplitProposal, propose_split (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/decomposition/test_splitter.py` on Windows and Linux once src/asf/m3_orchestration/decomposition/splitter.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/decomposition/test_splitter.py` and `uv run mypy tests/m3_orchestration/decomposition/test_splitter.py` are clean.

from types import SimpleNamespace
from typing import Any

import pytest

from asf.contracts.tasks import TaskNode
from asf.m3_orchestration.decomposition.splitter import SplitProposal, propose_split


def _parent(**over: object) -> TaskNode:
    base = {
        "id": "p1", "run_id": "r1", "kind": "composite", "goal": "billing module", "idempotency_key": "k", "depth": 1, "priority": 2,
        "acceptance_refs": ["charge works", "refund works"], "allowed_files": ["src/charge.py", "src/refund.py"], "deps": ["ledger"],
    }
    return TaskNode.model_validate({**base, **over})


SPLIT = {
    "children": [
        {"goal": "implement charge", "allowed_files": ["src/charge.py"], "acceptance_refs": ["charge works"], "contract_refs": ["billing@1"]},
        {"goal": "Implement   REFUND", "allowed_files": ["src/refund.py"], "acceptance_refs": ["refund works"], "deps": [1, 2, 9]},
    ],
    "new_contract_ids": ["c-refund"],
    "rationale": "one child per operation",
}


class _Gateway:
    def __init__(self, *replies: Any) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[Any, str, Any]] = []
        self.prompts: list[str] = []

    def model_for(self, role: Any, purpose: str, output_schema: Any = None, task_id: Any = None) -> Any:
        self.calls.append((role, purpose, task_id))
        outer = self

        class _Model:
            def invoke(self, prompt: str) -> Any:
                outer.prompts.append(prompt)
                return outer.replies.pop(0)

        return _Model()


def test_children_are_built_with_ids_parentage_and_inherited_scheduling_fields() -> None:
    proposal = propose_split(_parent(), gateway=_Gateway(SPLIT))  # type: ignore[arg-type]
    assert isinstance(proposal, SplitProposal)
    assert proposal.parent_id == "p1" and proposal.new_contract_ids == ["c-refund"] and proposal.rationale == "one child per operation"
    first, second = proposal.children
    assert (first.id, second.id) == ("p1.1", "p1.2")
    assert first.parent_id == "p1" and first.run_id == "r1" and first.depth == 2 and first.priority == 2
    assert first.state.value == "PROPOSED" and first.allowed_files == ["src/charge.py"] and first.contract_refs == ["billing@1"]


def test_sibling_dependencies_are_positions_and_the_parents_external_deps_are_inherited() -> None:
    first, second = propose_split(_parent(), gateway=_Gateway(SPLIT)).children  # type: ignore[arg-type]
    assert first.deps == ["ledger"]
    assert second.deps == ["p1.1", "ledger"]  # position 1 -> p1.1; self (2) and out-of-range (9) are ignored


def test_idempotency_keys_ignore_case_and_spacing_but_not_the_contract_slice() -> None:
    a = propose_split(_parent(), gateway=_Gateway(SPLIT)).children  # type: ignore[arg-type]
    b = propose_split(_parent(), gateway=_Gateway(SPLIT)).children  # type: ignore[arg-type]
    assert [c.idempotency_key for c in a] == [c.idempotency_key for c in b]
    assert len({c.idempotency_key for c in a}) == 2
    first_child: dict[str, Any] = dict(SPLIT["children"][0])  # type: ignore[index]
    other = {"children": [{**first_child, "contract_refs": ["billing@2"]}, SPLIT["children"][1]]}  # type: ignore[index]
    assert propose_split(_parent(), gateway=_Gateway(other)).children[0].idempotency_key != a[0].idempotency_key  # type: ignore[arg-type]


def test_the_planner_tier_is_asked_with_the_parent_goal_and_feedback() -> None:
    gateway = _Gateway(SPLIT)
    propose_split(_parent(), gateway=gateway, feedback="- file 'x' is owned twice", context="EXTRA CONTEXT")  # type: ignore[arg-type]
    assert gateway.calls == [("T3", "split_proposal", "p1")]
    assert "billing module" in gateway.prompts[0] and "file 'x' is owned twice" in gateway.prompts[0] and "EXTRA CONTEXT" in gateway.prompts[0]


def test_the_skill_body_is_added_and_a_missing_skill_is_tolerated() -> None:
    gateway = _Gateway(SPLIT)
    propose_split(_parent(), gateway=gateway, skills=SimpleNamespace(load_body=lambda n: "PROCEDURE BODY"))  # type: ignore[arg-type]
    assert "PROCEDURE BODY" in gateway.prompts[0]

    def missing(name: str) -> str:
        raise KeyError(name)

    propose_split(_parent(), gateway=_Gateway(SPLIT), skills=SimpleNamespace(load_body=missing))  # type: ignore[arg-type]


def test_invalid_replies_are_re_asked_then_raise() -> None:
    gateway = _Gateway({"children": "nope"}, SimpleNamespace(content="no json"), SPLIT)
    assert len(propose_split(_parent(), gateway=gateway).children) == 2  # type: ignore[arg-type]
    assert "invalid" in gateway.prompts[1]
    with pytest.raises(Exception) as info:  # noqa: PT011 - InvalidModelOutput lives in contracts
        propose_split(_parent(), gateway=_Gateway({"x": 1}, "a", {"children": 5}))  # type: ignore[arg-type]
    assert type(info.value).__name__ == "InvalidModelOutput"
