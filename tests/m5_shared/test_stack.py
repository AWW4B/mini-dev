# FILE: tests/m5_shared/test_stack.py
# ROLE: Tests that prove src/asf/m5_shared/stack.py meets its DONE WHEN conditions.
# ARCH REF: M3; p04 Escalation & Recovery; IF-10; A-3; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/stack.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/stack.py: StackContract, derive_stack, save_stack, find_stack, stack_prompt, foreign_imports (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/test_stack.py` on Windows and Linux once src/asf/m5_shared/stack.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/test_stack.py` and `uv run mypy tests/m5_shared/test_stack.py` are clean.

from pathlib import Path

from asf.m5_shared.stack import StackContract, derive_stack, find_stack, foreign_imports, save_stack, stack_prompt


def test_a_spec_without_libraries_gets_the_standard_library_and_argparse() -> None:
    stack = derive_stack("Build a small Python command line tool. src/wordfreq/core.py has top_words")
    assert stack.libraries == [] and stack.cli == "argparse" and stack.layout == "src"


def test_a_library_the_spec_names_is_allowed_and_becomes_the_cli() -> None:
    stack = derive_stack("A CLI built with Click that fetches pages with requests")
    assert stack.cli == "click" and set(stack.libraries) == {"click", "requests"}


def test_a_worktree_finds_the_projects_stack_and_the_prompt_names_it(tmp_path: Path) -> None:
    save_stack(tmp_path, StackContract())
    worktree = tmp_path / ".worktrees" / "task-1"
    worktree.mkdir(parents=True)
    found = find_stack(worktree)
    assert found is not None and "standard library only" in stack_prompt(found) and "argparse" in stack_prompt(found)


def test_imports_outside_the_stack_are_found_and_stdlib_project_and_pytest_in_tests_are_not() -> None:
    stack = StackContract()
    source = "import os\nimport click\nfrom wordfreq.core import top_words\nfrom . import x\nimport numpy as np\n"
    assert foreign_imports(source, stack, {"wordfreq"}) == ["click", "numpy"]
    assert foreign_imports("import pytest\n", stack, set(), is_test=True) == []
    assert foreign_imports("import pytest\n", stack, set()) == ["pytest"]
