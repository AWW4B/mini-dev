# FILE: src/asf/m5_shared/tools/builtin_tools.py
# ROLE: Implements the built-in tools (read, write, search, run tests, run linter, list files) as plain functions registered in the ToolRegistry.
# ARCH REF: M5; p12; IF-14
# OWNS: Built-in tool behaviour
# DOES NOT OWN: Permission checks (executor/policy run before these)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/tools/registry.py: ToolRegistry (registration)
#   - imports from src/asf/platform/select.py: get_platform (platform adapter)
#   - called by src/asf/m3_orchestration/acceptance.py: run_tests
#   - called by tests/m5_shared/tools/test_builtin_tools.py: read_file, write_file, search_code, run_tests, run_linter, register_builtin_tools
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. These functions assume the executor already checked policy; they still never follow symlinks outside the given root.
#   9. Use ripgrep when available (shutil.which) and a pure-Python fallback otherwise (D-30).
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/tools/test_builtin_tools.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/tools/builtin_tools.py` and `uv run mypy src/asf/m5_shared/tools/builtin_tools.py` are clean.

from pathlib import Path

from asf.m5_shared.tools.registry import ToolRegistry


def read_file(root: Path, rel_path: str) -> str:
    raise NotImplementedError


def write_file(root: Path, rel_path: str, content: str) -> None:
    raise NotImplementedError


def search_code(root: Path, pattern: str, max_hits: int = 50) -> list[str]:
    raise NotImplementedError


def run_tests(root: Path, selectors: list[str]) -> tuple[int, str]:
    raise NotImplementedError


def run_linter(root: Path, files: list[str]) -> tuple[int, str]:
    raise NotImplementedError


def register_builtin_tools(registry: ToolRegistry) -> None:
    raise NotImplementedError
