# FILE: tests/doctor/test_checks.py
# ROLE: Tests that prove src/asf/doctor/checks.py meets its DONE WHEN conditions.
# ARCH REF: FR-4 doctor; D-45; D-20 tier report; D-09 baseline warning; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/doctor/checks.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/doctor/checks.py: CheckStatus, CheckResult, run_all_checks (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/doctor/test_checks.py` on Windows and Linux once src/asf/doctor/checks.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/doctor/test_checks.py` and `uv run mypy tests/doctor/test_checks.py` are clean.


from asf.doctor.checks import CheckResult, CheckStatus, run_all_checks  # noqa: F401


def test_check_status_meets_contract() -> None:
    """Prove CheckStatus behaves as declared in src/asf/doctor/checks.py."""
    raise NotImplementedError("write this test before implementing CheckStatus")

def test_check_result_meets_contract() -> None:
    """Prove CheckResult behaves as declared in src/asf/doctor/checks.py."""
    raise NotImplementedError("write this test before implementing CheckResult")

def test_run_all_checks_meets_contract() -> None:
    """Prove run_all_checks behaves as declared in src/asf/doctor/checks.py."""
    raise NotImplementedError("write this test before implementing run_all_checks")
