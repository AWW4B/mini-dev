# FILE: tests/m3_orchestration/test_acceptance.py
# ROLE: Tests that prove src/asf/m3_orchestration/acceptance.py meets its DONE WHEN conditions.
# ARCH REF: M3; p04 final acceptance; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/acceptance.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/acceptance.py: AcceptanceResult, final_acceptance (unit under test)
#   - imports from src/asf/contracts/requests.py: StructuredRequest (used here)
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (used here)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/test_acceptance.py` on Windows and Linux once src/asf/m3_orchestration/acceptance.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/test_acceptance.py` and `uv run mypy tests/m3_orchestration/test_acceptance.py` are clean.

from pathlib import Path

from asf.contracts.requests import StructuredRequest
from asf.m3_orchestration.acceptance import AcceptanceResult, final_acceptance
from asf.m5_shared.workspace.blobs import BlobStore


def _request(*req_ids: str) -> StructuredRequest:
    return StructuredRequest.model_validate(
        {
            "request_id": "q1", "project_id": "p", "task_type": "new_build",
            "requirements": [{"req_id": r, "text": f"text of {r}", "source_ref": "prompt"} for r in req_ids],
        }
    )


def _project(tmp_path: Path, **tests: str) -> Path:
    for rel, text in tests.items():
        path = tmp_path / (rel.replace("__", "/") + ".py")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def _regression(code: int = 0, out: str = "3 passed"):  # type: ignore[no-untyped-def]
    calls: list[tuple[Path, list[str]]] = []

    def run(root: Path, selectors: list[str]) -> tuple[int, str]:
        calls.append((root, selectors))
        return code, out

    run.calls = calls  # type: ignore[attr-defined]
    return run


def test_green_when_every_requirement_is_traced_and_the_regression_passes(tmp_path: Path) -> None:
    root = _project(tmp_path, tests__test_a="# REQ-1 login\n", tests__test_b="def test_x(): ...  # covers REQ-2\n")
    blobs = BlobStore(tmp_path / "blobs")
    regression = _regression()
    result = final_acceptance(_request("REQ-1", "REQ-2"), root, regression=regression, blobs=blobs)
    assert isinstance(result, AcceptanceResult)
    assert result.passed and result.untraced == [] and result.failing_tests == []
    assert regression.calls == [(root, [])]
    report = blobs.get(result.report_ref).decode()
    assert "REQ-1\ttraced" in report and "Regression exit code: 0" in report


def test_an_untraced_requirement_fails_acceptance_even_when_tests_pass(tmp_path: Path) -> None:
    root = _project(tmp_path, tests__test_a="# REQ-1\n")
    result = final_acceptance(_request("REQ-1", "REQ-9"), root, regression=_regression(), blobs=BlobStore(tmp_path / "b"))
    assert not result.passed and result.untraced == ["REQ-9"]
    assert "REQ-9\tUNTRACED" in BlobStore(tmp_path / "b").get(result.report_ref).decode()


def test_a_failing_regression_fails_acceptance_and_lists_the_failing_tests(tmp_path: Path) -> None:
    root = _project(tmp_path, tests__test_a="# REQ-1\n")
    out = "FAILED tests/test_a.py::test_one - assert 0\nERROR tests/test_b.py::test_two\nFAILED tests/test_a.py::test_one - again\n"
    result = final_acceptance(_request("REQ-1"), root, regression=_regression(1, out), blobs=BlobStore(tmp_path / "b"))
    assert not result.passed and result.untraced == []
    assert result.failing_tests == ["tests/test_a.py::test_one", "tests/test_b.py::test_two"]


def test_only_test_files_count_as_traceability(tmp_path: Path) -> None:
    root = _project(tmp_path, src__module="# REQ-1 is mentioned in source, not in a test\n")
    result = final_acceptance(_request("REQ-1"), root, regression=_regression(), blobs=BlobStore(tmp_path / "b"))
    assert result.untraced == ["REQ-1"]


def test_vendored_directories_are_not_scanned(tmp_path: Path) -> None:
    root = _project(tmp_path, node_modules__tests__test_dep="# REQ-1\n", tests__test_a="# nothing\n")
    result = final_acceptance(_request("REQ-1"), root, regression=_regression(), blobs=BlobStore(tmp_path / "b"))
    assert result.untraced == ["REQ-1"]


def test_no_requirements_means_the_matrix_is_vacuously_green(tmp_path: Path) -> None:
    result = final_acceptance(_request(), tmp_path, regression=_regression(), blobs=BlobStore(tmp_path / "b"))
    assert result.passed and result.untraced == []
