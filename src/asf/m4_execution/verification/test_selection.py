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

from pathlib import Path

from asf.contracts.outcomes import ChangeSet
from asf.m5_shared.context.repo_index import RepoIndex


def _is_test_path(path: str) -> bool:
    p = Path(path)
    return p.name.startswith("test_") or "tests" in p.parts


def _is_contract_test(path: str) -> bool:
    lowered = path.lower()
    return _is_test_path(path) and ("contract" in lowered)


def select_tests(change: ChangeSet, acceptance_refs: list[str], *, index: RepoIndex | None = None) -> list[str]:
    """Task acceptance tests first, then contract tests of touched interfaces, then tests mapped to the touched sources.

    The result is de-duplicated and keeps that order. ``index`` may be passed to reuse an already built RepoIndex.
    """
    repo_index = index if index is not None else RepoIndex(Path(change.worktree_path))
    touched = [Path(p).as_posix() for p in change.files_touched]
    touched_sources = [p for p in touched if not _is_test_path(p)]

    selected: list[str] = list(acceptance_refs)

    # Contract tests of touched interfaces: contract tests that mention a touched module by name.
    for source in touched_sources:
        stem = Path(source).stem
        selected.extend(hit for hit in repo_index.search(stem, max_hits=50) if _is_contract_test(hit))

    # Tests the change touched itself, and tests mapped to the touched sources.
    selected.extend(p for p in touched if _is_test_path(p))
    selected.extend(repo_index.tests_for(touched_sources))

    return list(dict.fromkeys(selected))
