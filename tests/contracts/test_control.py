# FILE: tests/contracts/test_control.py
# ROLE: Tests that prove src/asf/contracts/control.py meets its DONE WHEN conditions.
# ARCH REF: p04 Run Control; IF-05; IF-06; D-15; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/control.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/control.py: RunCommand, RunControl, CancelSignal (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_control.py` on Windows and Linux once src/asf/contracts/control.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_control.py` and `uv run mypy tests/contracts/test_control.py` are clean.


from asf.contracts.control import CancelSignal, RunCommand, RunControl  # noqa: F401


def test_run_command_meets_contract() -> None:
    """Prove RunCommand behaves as declared in src/asf/contracts/control.py."""
    raise NotImplementedError("write this test before implementing RunCommand")

def test_run_control_meets_contract() -> None:
    """Prove RunControl behaves as declared in src/asf/contracts/control.py."""
    raise NotImplementedError("write this test before implementing RunControl")

def test_cancel_signal_meets_contract() -> None:
    """Prove CancelSignal behaves as declared in src/asf/contracts/control.py."""
    raise NotImplementedError("write this test before implementing CancelSignal")
