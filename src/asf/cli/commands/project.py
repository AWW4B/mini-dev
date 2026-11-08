# FILE: src/asf/cli/commands/project.py
# ROLE: Implements `factory project new|list|show`.
# ARCH REF: M1; p02 Project History; IF-24
# OWNS: Argument parsing and output for this command group
# DOES NOT OWN: Business logic (lives in the imported modules)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (read-only queries / command rows)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - called by src/asf/cli/app.py: register
#   - called by tests/cli/commands/test_project.py: project_new, project_list, project_show, register
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Never run agents or keep execution state in the CLI; write commands to the command table (IF-05) and read state/events (M1 is a thin client).
#   9. Support --output rich|plain|json through Renderer; prompts only when stdin and stdout are TTYs, otherwise exit 2 naming the missing flags (D-13).
#   10. Exit codes: 0 success, 1 user/validation error, 2 environment problem.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/cli/commands/test_project.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/commands/project.py` and `uv run mypy src/asf/cli/commands/project.py` are clean.

from pathlib import Path

import typer


def project_new(name: str, path: Path) -> int:
    raise NotImplementedError


def project_list(output: str = "rich") -> int:
    raise NotImplementedError


def project_show(project: str, output: str = "rich") -> int:
    raise NotImplementedError


def register(app: typer.Typer) -> None:
    """Attach the `project` command(s) to the root Typer app."""
    raise NotImplementedError
