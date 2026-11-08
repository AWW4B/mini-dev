# FILE: src/asf/m5_shared/context/repo_index.py
# ROLE: Builds and queries the static code index (tree-sitter symbols, imports, test<->source map).
# ARCH REF: M5; p12; D-30
# OWNS: Index build and query
# DOES NOT OWN: Deciding what goes into a prompt (context_service)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/platform/select.py: get_platform (platform adapter)
#   - called by src/asf/m5_shared/context/context_service.py: RepoIndex
#   - called by src/asf/m2_request/repository_intake.py: RepoIndex
#   - called by src/asf/m4_execution/verification/test_selection.py: RepoIndex
#   - called by tests/m5_shared/context/test_repo_index.py: RepoIndex
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/context/test_repo_index.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/context/repo_index.py` and `uv run mypy src/asf/m5_shared/context/repo_index.py` are clean.

from pathlib import Path


class RepoIndex:
    def build(self, root: Path) -> None:
        raise NotImplementedError

    def symbols_for(self, rel_paths: list[str]) -> list[str]:
        raise NotImplementedError

    def tests_for(self, rel_paths: list[str]) -> list[str]:
        raise NotImplementedError

    def search(self, text: str, max_hits: int = 20) -> list[str]:
        raise NotImplementedError
