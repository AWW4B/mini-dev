# FILE: src/asf/m4_execution/verification/test_selection.py
# ROLE: Selects tests for a change: task acceptance tests plus contract tests of touched interfaces plus mapped source tests.
# ARCH REF: M4; p08 select tests
# OWNS: Test selection
# DOES NOT OWN: Running tests
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/context/repo_index.py: RepoIndex (test map)
#   - imports from src/asf/contracts/outcomes.py: ChangeSet (input)
#   - called by src/asf/m4_execution/verification/gate.py: select_tests
#   - called by tests/m4_execution/verification/test_test_selection.py: select_tests
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m4_execution/verification/test_test_selection.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m4_execution/verification/test_selection.py` and `uv run mypy src/asf/m4_execution/verification/test_selection.py` are clean.

from asf.contracts.outcomes import ChangeSet


def select_tests(change: ChangeSet, acceptance_refs: list[str]) -> list[str]:
    raise NotImplementedError
