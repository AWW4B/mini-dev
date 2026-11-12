# FILE: tests/m4_execution/verification/test_test_selection.py
# ROLE: Tests that prove src/asf/m4_execution/verification/test_selection.py meets its DONE WHEN conditions.
# ARCH REF: M4; p08 select tests; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m4_execution/verification/test_selection.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m4_execution/verification/test_selection.py: select_tests (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m4_execution/verification/test_test_selection.py` on Windows and Linux once src/asf/m4_execution/verification/test_selection.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m4_execution/verification/test_test_selection.py` and `uv run mypy tests/m4_execution/verification/test_test_selection.py` are clean.

from pathlib import Path

from asf.m4_execution.verification.test_selection import select_tests


def _write(root: Path, rel: str, text: str = "x = 1\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _change(root: Path, touched: list[str]) -> object:
    class _Change:
        worktree_path = str(root)
        files_touched = touched

    return _Change()


def test_acceptance_tests_come_first_then_contract_then_mapped_tests(tmp_path: Path) -> None:
    _write(tmp_path, "src/billing.py", "def charge(): pass\n")
    _write(tmp_path, "tests/test_billing.py", "def test_charge(): pass\n")
    _write(tmp_path, "tests/contracts/test_billing_contract.py", "from billing import charge\n")
    _write(tmp_path, "tests/test_unrelated.py")

    selected = select_tests(_change(tmp_path, ["src/billing.py"]), ["tests/acceptance/test_checkout.py"])  # type: ignore[arg-type]

    assert selected[0] == "tests/acceptance/test_checkout.py"
    assert "tests/contracts/test_billing_contract.py" in selected
    assert "tests/test_billing.py" in selected
    assert selected.index("tests/contracts/test_billing_contract.py") < selected.index("tests/test_billing.py")
    assert "tests/test_unrelated.py" not in selected


def test_a_touched_test_file_is_selected_and_nothing_is_duplicated(tmp_path: Path) -> None:
    _write(tmp_path, "src/billing.py")
    _write(tmp_path, "tests/test_billing.py")
    selected = select_tests(_change(tmp_path, ["src/billing.py", "tests/test_billing.py"]), ["tests/test_billing.py"])  # type: ignore[arg-type]
    assert selected.count("tests/test_billing.py") == 1


def test_no_touched_sources_and_no_acceptance_selects_nothing(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "hello\n")
    assert select_tests(_change(tmp_path, ["README.md"]), []) == []  # type: ignore[arg-type]
