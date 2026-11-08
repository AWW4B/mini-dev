# FILE: tests/cli/test_app.py
# ROLE: Tests that prove src/asf/cli/app.py meets its DONE WHEN conditions.
# ARCH REF: M1; p01 HLD; p02; D-11; D-12; D-13; D-40; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/app.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/app.py: main (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/test_app.py` on Windows and Linux once src/asf/cli/app.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/test_app.py` and `uv run mypy tests/cli/test_app.py` are clean.


from asf.cli.app import main  # noqa: F401


def test_main_meets_contract() -> None:
    """Prove main behaves as declared in src/asf/cli/app.py."""
    raise NotImplementedError("write this test before implementing main")
