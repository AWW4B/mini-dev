# FILE: tests/m2_request/test_request_understanding.py
# ROLE: Tests that prove src/asf/m2_request/request_understanding.py meets its DONE WHEN conditions.
# ARCH REF: M2; p03 Request Understanding; IF-02; IF-03 clarify; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m2_request/request_understanding.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m2_request/request_understanding.py: understand_request (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m2_request/test_request_understanding.py` on Windows and Linux once src/asf/m2_request/request_understanding.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m2_request/test_request_understanding.py` and `uv run mypy tests/m2_request/test_request_understanding.py` are clean.

from types import SimpleNamespace
from typing import Any

from asf.m2_request.request_understanding import understand_request


def test_understand_request_meets_contract() -> None:
    """Prove understand_request behaves as declared in src/asf/m2_request/request_understanding.py."""
    # 1. Debug request
    req1 = understand_request(
        request_id="req-001",
        prompt="Fix the failing test in auth service",
        document_refs=[],
        repo_profile=None,
    )
    assert req1.request_id == "req-001"
    assert req1.task_type.value == "debug"
    assert len(req1.requirements) >= 1
    assert req1.requirements[0].req_id.startswith("REQ-")
    assert req1.requirements[0].source_ref == "prompt"

    # 2. Feature request with multiple requirements and documents
    fake_profile: Any = SimpleNamespace(
        languages=["python"],
        build_commands=[["uv", "sync"]],
        test_commands=[["pytest"]],
        baseline_passed=[],
        baseline_failed=[],
        index_ref="index:123",
        supported=True,
    )
    prompt2 = (
        "- Implement user profile update endpoint\n"
        "- Send notification email on profile change\n"
        "Must respond within 200ms\n"
    )
    req2 = understand_request(
        request_id="req-002",
        prompt=prompt2,
        document_refs=["sha256:spec_doc"],
        repo_profile=fake_profile,
    )
    assert req2.request_id == "req-002"
    assert req2.task_type.value == "feature"
    assert len(req2.requirements) >= 2
    assert req2.requirements[0].source_ref == "sha256:spec_doc"
    assert req2.repo_profile is not None
