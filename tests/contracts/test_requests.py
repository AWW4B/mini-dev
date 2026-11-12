# FILE: tests/contracts/test_requests.py
# ROLE: Tests that prove src/asf/contracts/requests.py meets its DONE WHEN conditions.
# ARCH REF: p02 Project Input; p03 Request Processing; IF-01; IF-02; D-29; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/requests.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/requests.py: TaskType, SubmitRequest, Requirement, RepoProfile, StructuredRequest (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_requests.py` on Windows and Linux once src/asf/contracts/requests.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_requests.py` and `uv run mypy tests/contracts/test_requests.py` are clean.



import pytest
from pydantic import ValidationError

from asf.contracts.requests import RepoProfile, Requirement, StructuredRequest, SubmitRequest, TaskType


def test_task_types_include_the_unsupported_marker() -> None:
    assert {t.value for t in TaskType} == {
        "new_build", "debug", "feature", "refactor", "test_generation", "code_docs", "unsupported",
    }


def test_submit_request_defaults() -> None:
    req = SubmitRequest.model_validate({"project_id": "p1", "text": "build a todo app"})
    assert req.attachment_refs == []
    assert req.repo_ref is None
    assert req.mode_hint is None


def test_submit_request_mode_hint_must_be_a_task_type() -> None:
    assert SubmitRequest.model_validate({"project_id": "p1", "text": "x", "mode_hint": "debug"}).mode_hint is TaskType.DEBUG
    with pytest.raises(ValidationError):
        SubmitRequest.model_validate({"project_id": "p1", "text": "x", "mode_hint": "poetry"})


def test_submit_request_requires_text() -> None:
    with pytest.raises(ValidationError):
        SubmitRequest.model_validate({"project_id": "p1"})


def test_requirement_requires_anchor_text_and_source() -> None:
    req = Requirement.model_validate({"req_id": "REQ-1", "text": "must log in", "source_ref": "spec.md#1"})
    assert req.req_id == "REQ-1"
    with pytest.raises(ValidationError):
        Requirement.model_validate({"req_id": "REQ-1", "text": "must log in"})


def test_repo_profile_commands_are_argument_lists_not_shell_strings() -> None:
    ok = RepoProfile.model_validate({"languages": ["python"], "build_commands": [["uv", "sync"]], "test_commands": [["pytest", "-q"]]})
    assert ok.supported is True
    assert ok.baseline_passed == [] and ok.baseline_failed == [] and ok.index_ref is None
    with pytest.raises(ValidationError):
        RepoProfile.model_validate({"languages": ["python"], "build_commands": ["uv sync"], "test_commands": []})


def test_structured_request_defaults_and_nested_profile() -> None:
    sr = StructuredRequest.model_validate({
        "request_id": "q1", "project_id": "p1", "task_type": "feature",
        "requirements": [{"req_id": "REQ-1", "text": "t", "source_ref": "s"}],
    })
    assert sr.constraints == [] and sr.nfrs == [] and sr.acceptance == []
    assert sr.assumptions == [] and sr.open_questions == []
    assert sr.repo_profile is None
    with_profile = StructuredRequest.model_validate({
        "request_id": "q1", "project_id": "p1", "task_type": "debug", "requirements": [],
        "repo_profile": {"languages": ["python"], "build_commands": [], "test_commands": [["pytest"]]},
    })
    assert with_profile.repo_profile is not None and with_profile.repo_profile.test_commands == [["pytest"]]
    assert StructuredRequest.model_validate_json(with_profile.model_dump_json()) == with_profile
