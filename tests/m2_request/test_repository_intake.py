# FILE: tests/m2_request/test_repository_intake.py
# ROLE: Tests that prove src/asf/m2_request/repository_intake.py meets its DONE WHEN conditions.
# ARCH REF: M2; p03 Repository Intake; D-29 (git subprocess + intake_rules.toml; v1 Python); D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m2_request/repository_intake.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m2_request/repository_intake.py: intake_repository (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m2_request/test_repository_intake.py` on Windows and Linux once src/asf/m2_request/repository_intake.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m2_request/test_repository_intake.py` and `uv run mypy tests/m2_request/test_repository_intake.py` are clean.

from pathlib import Path
from typing import Any

import pytest

import asf.m2_request.repository_intake as intake_mod
from asf.m2_request.repository_intake import intake_repository


def test_intake_repository_meets_contract(tmp_path: Path, fake_paths: Any) -> None:
    """Prove intake_repository behaves as declared in src/asf/m2_request/repository_intake.py."""
    _ = fake_paths

    # Set up a sample Python project
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "sample-proj"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "app.py").write_text("def run() -> None:\n    pass\n", encoding="utf-8")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_app.py").write_text(
        "def test_run() -> None:\n    assert True\n",
        encoding="utf-8",
    )

    profile = intake_repository(str(tmp_path), project_id="proj_123")

    assert "python" in profile.languages
    assert len(profile.build_commands) >= 1
    assert any("uv" in cmd or "pip" in cmd or "python" in cmd for cmd in profile.build_commands)
    assert len(profile.test_commands) >= 1
    assert profile.supported is True
    assert profile.index_ref is not None


def test_detection_ignores_vendored_directories(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    (tmp_path / "app.rs").write_text("fn main() {}\n", encoding="utf-8")
    vendored = tmp_path / "node_modules" / "dep"
    vendored.mkdir(parents=True)
    (vendored / "index.js").write_text("module.exports = 1;\n", encoding="utf-8")
    venv = tmp_path / ".venv" / "lib"
    venv.mkdir(parents=True)
    (venv / "x.py").write_text("x = 1\n", encoding="utf-8")

    profile = intake_repository(str(tmp_path), project_id="p")
    assert profile.languages == ["rust"]


def test_missing_repository_is_reported_unsupported(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    profile = intake_repository(str(tmp_path / "nope"), project_id="p")
    assert profile.supported is False
    assert profile.languages == [] and profile.test_commands == []


def test_baseline_tests_do_not_run_without_a_real_sandbox(
    tmp_path: Path, fake_paths: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = fake_paths
    marker = tmp_path / "ran.txt"
    (tmp_path / "test_marker.py").write_text(
        f"from pathlib import Path\n\ndef test_x() -> None:\n    Path({str(marker)!r}).write_text('ran', encoding='utf-8')\n",
        encoding="utf-8",
    )

    class _NoSandbox:
        tier = "C"

        def available(self) -> bool:
            return False

        def run(self, spec: Any) -> Any:
            raise AssertionError("the repository must not be executed without a tier-A sandbox")

    class _Platform:
        def sandbox(self) -> _NoSandbox:
            return _NoSandbox()

    monkeypatch.setattr(intake_mod, "get_platform", lambda: _Platform())
    profile = intake_repository(str(tmp_path), project_id="p")
    assert profile.test_commands
    assert profile.baseline_passed == [] and profile.baseline_failed == []
    assert not marker.exists()


@pytest.mark.parametrize(
    ("exit_code", "timed_out", "passed", "failed"),
    [(0, False, ["all_tests"], []), (1, False, [], ["some_tests_failed"]), (-9, True, [], ["baseline_timeout"])],
)
def test_baseline_result_comes_from_the_sandbox_run(
    tmp_path: Path, fake_paths: Any, monkeypatch: pytest.MonkeyPatch, exit_code: int, timed_out: bool, passed: list[str], failed: list[str]
) -> None:
    _ = fake_paths
    (tmp_path / "test_ok.py").write_text("def test_ok() -> None:\n    pass\n", encoding="utf-8")
    seen: list[Any] = []

    class _Result:
        def __init__(self) -> None:
            self.exit_code = exit_code
            self.timed_out = timed_out

    class _Sandbox:
        tier = "A"

        def available(self) -> bool:
            return True

        def run(self, spec: Any) -> Any:
            seen.append(spec)
            return _Result()

    class _Platform:
        def sandbox(self) -> _Sandbox:
            return _Sandbox()

    monkeypatch.setattr(intake_mod, "get_platform", lambda: _Platform())
    profile = intake_repository(str(tmp_path), project_id="p")
    assert (profile.baseline_passed, profile.baseline_failed) == (passed, failed)
    assert seen[0].network is False
    assert seen[0].cwd == tmp_path
