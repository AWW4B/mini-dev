# FILE: src/asf/cli/commands/init.py
# ROLE: Implements `factory init`: creates the user config dir files and the project .factory dir with defaults.
# ARCH REF: D-37; D-12
# OWNS: Argument parsing and output for this command group
# DOES NOT OWN: Business logic (lives in the imported modules)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/paths.py: AppPaths, get_paths (cross-platform base directories)
#   - imports from src/asf/config/loader.py: write_user_toml (write defaults)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: EXIT_OK, default_output, guard, register_project, renderer_for (shared CLI plumbing)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (creates the project's state.db)
#   - called by src/asf/cli/app.py: register
#   - called by tests/cli/commands/test_init.py: init, register
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
# DONE WHEN: (1) tests/cli/commands/test_init.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/commands/init.py` and `uv run mypy src/asf/cli/commands/init.py` are clean.

import importlib.resources
import tomllib
from pathlib import Path
from typing import Any

import typer

from asf.cli.context import EXIT_OK, default_output, guard, register_project, renderer_for
from asf.config.loader import write_user_toml
from asf.config.paths import get_paths
from asf.m5_shared.state_store.store import StateStore

_USER_FILES = ("factory", "models")  # the settings a user is expected to edit


def _packaged_defaults(name: str) -> dict[str, Any]:
    """The defaults shipped with the software, without the user's own edits layered on top."""
    raw = importlib.resources.files("asf.config.defaults").joinpath(f"{name}.toml").read_bytes()
    return tomllib.loads(raw.decode("utf-8"))


def init(project_root: Path | None = None, force: bool = False, output: str | None = None) -> int:
    """Create the user config files (from the packaged defaults) and this project's .factory directory."""
    root = (project_root or Path.cwd()).resolve()
    paths = get_paths()
    created: list[str] = []

    for name in _USER_FILES:
        target = paths.config_dir / f"{name}.toml"
        if force or not target.exists():
            write_user_toml(name, _packaged_defaults(name))
            created.append(str(target))

    factory_dir = paths.project_dir(root)
    state_db = paths.state_db(root)
    if not state_db.exists():
        StateStore.open(state_db).close()
        created.append(str(state_db))
    ignore = factory_dir / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")  # run state, blobs and logs never go into the project's git history
        created.append(str(ignore))
    register_project(root.name, root)

    renderer = renderer_for(output or default_output())
    renderer.record(
        "Factory project ready",
        {"project": root.name, "directory": str(root), "created": ", ".join(created) or "nothing new (already initialised)", "next": "factory doctor, then factory run start"},
    )
    return EXIT_OK


def register(app: typer.Typer) -> None:
    """Attach the `init` command(s) to the root Typer app."""

    @app.command("init", help="Set up the user config and this directory as a factory project.")
    def init_cmd(
        path: Path | None = typer.Option(None, "--path", help="Project directory (default: here)"),
        force: bool = typer.Option(False, "--force", help="Overwrite the user config files with the packaged defaults"),
        output: str = typer.Option("rich", "--output", "-o", help="rich | plain | json"),
    ) -> None:
        raise typer.Exit(code=guard(lambda: init(path, force, output)))
