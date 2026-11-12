# FILE: tests/m3_orchestration/planning/test_test_authoring.py
# ROLE: Tests that prove src/asf/m3_orchestration/planning/test_authoring.py meets its DONE WHEN conditions.
# ARCH REF: M3; p05; A-4; D-10; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/planning/test_authoring.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/planning/test_authoring.py: author_acceptance_tests (unit under test)
#   - imports from src/asf/contracts/errors.py: ProviderUnavailable (fake gateway failure)
#   - imports from src/asf/contracts/tasks.py: TaskNode (the leaf under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/planning/test_test_authoring.py` on Windows and Linux once src/asf/m3_orchestration/planning/test_authoring.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/planning/test_test_authoring.py` and `uv run mypy tests/m3_orchestration/planning/test_test_authoring.py` are clean.

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from asf.contracts.errors import ProviderUnavailable
from asf.contracts.tasks import TaskNode
from asf.m3_orchestration.planning.test_authoring import author_acceptance_tests


def _node() -> TaskNode:
    return TaskNode.model_validate(
        {
            "id": "t1", "run_id": "r1", "kind": "leaf", "goal": "refund a payment", "idempotency_key": "k",
            "acceptance_refs": ["refund returns a receipt"], "contract_refs": ["ledger@1.0.0"], "allowed_files": ["src/refund.py"],
        }
    )


class _Gateway:
    def __init__(self, files: dict[str, str] | None = None, t3_down: bool = False) -> None:
        self.files = files if files is not None else {"tests/test_refund.py": "def test_refund():\n    assert True\n"}
        self.t3_down = t3_down
        self.calls: list[tuple[str, str]] = []
        self.prompts: list[str] = []

    def model_for(self, role: Any, purpose: str, output_schema: Any = None, task_id: Any = None) -> Any:
        self.calls.append((role, purpose))
        if role == "T3" and self.t3_down:
            raise ProviderUnavailable("planner tier is down")
        outer = self

        class _Model:
            def invoke(self, prompt: str) -> Any:
                outer.prompts.append(prompt)
                return {"files": outer.files}

        return _Model()


class _Broker:
    def __init__(self) -> None:
        self.requests: list[Any] = []

    def request(self, req: Any) -> None:
        self.requests.append(req)


def _author(tmp_path: Path, gateway: _Gateway, allow_local: bool = False, **kwargs: Any) -> list[str]:
    return author_acceptance_tests(_node(), allow_local, gateway=gateway, project_root=tmp_path, **kwargs)  # type: ignore[arg-type]


def test_t3_writes_the_tests_and_the_paths_are_returned_relative_and_posix(tmp_path: Path) -> None:
    gateway = _Gateway({"tests/billing/test_refund.py": "def test_a(): ...\n", "tests/test_other.py": "x = 1\n"})
    paths = _author(tmp_path, gateway)
    assert paths == ["tests/billing/test_refund.py", "tests/test_other.py"]
    assert (tmp_path / "tests" / "billing" / "test_refund.py").read_text(encoding="utf-8") == "def test_a(): ...\n"
    assert gateway.calls == [("T3", "acceptance_tests")]
    assert "refund a payment" in gateway.prompts[0] and "ledger@1.0.0" in gateway.prompts[0]


@pytest.mark.parametrize("bad", ["../escape/test_x.py", "/abs/test_x.py", "src/test_x.py", "tests/helper.py", "tests/test_x.txt", "tests/../../test_x.py"])
def test_unsafe_or_misplaced_paths_are_rejected_and_nothing_is_written(tmp_path: Path, bad: str) -> None:
    with pytest.raises(Exception) as info:  # noqa: PT011 - InvalidModelOutput lives in contracts, which this test does not import
        _author(tmp_path, _Gateway({bad: "x = 1\n"}))
    assert type(info.value).__name__ == "InvalidModelOutput"
    assert not any(p.is_file() for p in tmp_path.rglob("*") if p.suffix == ".py")


def test_no_files_from_the_model_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(Exception) as info:  # noqa: PT011
        _author(tmp_path, _Gateway({}))
    assert type(info.value).__name__ == "InvalidModelOutput"


def test_t3_unavailable_without_the_switch_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ProviderUnavailable):
        _author(tmp_path, _Gateway(t3_down=True), allow_local=False)


def test_t3_unavailable_with_the_switch_asks_for_approval_first(tmp_path: Path) -> None:
    broker = _Broker()
    with pytest.raises(Exception) as info:  # noqa: PT011 - ApprovalRequired lives in contracts
        _author(tmp_path, _Gateway(t3_down=True), allow_local=True, broker=broker)
    assert type(info.value).__name__ == "ApprovalRequired"
    (req,) = broker.requests
    assert req.kind.value == "approve_local_tests" and req.task_id == "t1" and req.default_on_timeout is None
    assert not (tmp_path / "tests").exists()


def test_after_approval_a_local_draft_is_written_by_t2_never_t1(tmp_path: Path) -> None:
    gateway = _Gateway(t3_down=True)
    paths = _author(tmp_path, gateway, allow_local=True, broker=_Broker(), local_approved=True)
    assert paths == ["tests/test_refund.py"]
    assert [c[0] for c in gateway.calls] == ["T3", "T2"]
    assert all(role != "T1" for role, _ in gateway.calls)


def test_the_skill_body_is_added_when_available_and_a_missing_skill_is_tolerated(tmp_path: Path) -> None:
    gateway = _Gateway()
    skills = SimpleNamespace(load_body=lambda name: "STEP 1: derive one test per criterion")
    _author(tmp_path, gateway, skills=skills)
    assert "STEP 1: derive one test per criterion" in gateway.prompts[0]

    def missing(name: str) -> str:
        raise KeyError(name)

    other = _Gateway()
    _author(tmp_path / "second", other, skills=SimpleNamespace(load_body=missing))
    assert "PROCEDURE" not in other.prompts[0]
