# FILE: src/asf/cli/context.py
# ROLE: Resolves the current project, opens its state store and renders output: the small shared plumbing of the CLI commands.
# ARCH REF: M1; p02; D-13; D-15
# OWNS: Project root, store opening, exit codes, run id defaults
# DOES NOT OWN: Command behaviour (commands/*.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (output modes)
#   - imports from src/asf/contracts/errors.py: ConfigError (no project, bad output mode)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (the project's state.db)
#   - imports from src/asf/config/paths.py: get_paths (the project registry lives in the data dir)
#   - called by tests/cli/test_context.py: EXIT_OK, EXIT_USER, EXIT_ENV, project_root, state_db, open_store, renderer_for, latest_run_id, resolve_run_id
#   - called by src/asf/cli/run_controls.py: open_store
#   - called by src/asf/cli/views/task_tree_view.py: open_store, resolve_run_id
#   - called by src/asf/cli/views/inbox_view.py: open_store, resolve_run_id
#   - called by src/asf/cli/views/trace_view.py: open_store, resolve_run_id
#   - called by src/asf/cli/views/dash_view.py: open_store, resolve_run_id
#   - called by src/asf/cli/commands/doctor.py: guard, renderer_for
#   - called by src/asf/cli/commands/init.py: EXIT_OK, default_output, guard, register_project, renderer_for
#   - called by src/asf/cli/commands/project.py: EXIT_OK, EXIT_USER, guard, load_projects, register_project, renderer_for, state_db
#   - called by src/asf/cli/commands/config_cmd.py: EXIT_OK, EXIT_USER, guard, project_root, renderer_for
#   - called by src/asf/cli/commands/skills.py: EXIT_OK, EXIT_USER, guard, renderer_for
#   - called by src/asf/cli/commands/mcp.py: EXIT_OK, EXIT_USER, guard, project_root, renderer_for
#   - called by src/asf/cli/commands/models.py: EXIT_OK, EXIT_USER, guard, project_root, renderer_for
#   - called by src/asf/cli/commands/run.py: EXIT_ENV, EXIT_OK, EXIT_USER, default_output, guard, open_store, project_id_for, project_root, renderer_for, resolve_run_id
#   - called by src/asf/cli/commands/inbox.py: EXIT_OK, EXIT_USER, default_output, guard, open_store, renderer_for
#   - called by src/asf/cli/commands/history.py: EXIT_OK, EXIT_USER, guard, open_store, renderer_for
#   - called by src/asf/cli/commands/report.py: EXIT_OK, EXIT_USER, guard, open_store, renderer_for, resolve_run_id
#   - called by src/asf/cli/commands/stats.py: EXIT_OK, EXIT_USER, guard, open_store, renderer_for, resolve_run_id
#   - called by src/asf/cli/commands/events.py: EXIT_OK, EXIT_USER, guard, open_store, renderer_for, resolve_run_id
#   - called by src/asf/cli/commands/dash.py: EXIT_OK, default_output, guard, renderer_for
#   - called by src/asf/cli/commands/tasks.py: EXIT_OK, EXIT_USER, guard, open_store, renderer_for
#   - called by src/asf/cli/commands/trace.py: EXIT_OK, EXIT_USER, default_output, guard, renderer_for
#   - called by src/asf/cli/commands/web.py: EXIT_ENV, EXIT_OK, guard, renderer_for
#   - called by src/asf/cli/flows.py: EXIT_OK, EXIT_USER, open_store
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/cli/test_context.py pass on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/context.py` and `uv run mypy src/asf/cli/context.py` are clean.

import json
import sys
from collections.abc import Callable
from pathlib import Path

from asf.cli.ui.render import OutputMode, Renderer
from asf.config.paths import get_paths
from asf.contracts.errors import AsfError, ConfigError
from asf.m5_shared.state_store.store import StateStore

EXIT_OK = 0
EXIT_USER = 1  # the user's input was wrong
EXIT_ENV = 2  # the environment is the problem (no project, missing extra, no terminal)


class NoProjectError(ConfigError):
    """There is no factory project in the current directory."""


def project_root() -> Path:
    """The project is the current directory, as with git: its state lives in ./.factory/."""
    return Path.cwd().resolve()


def state_db(root: Path | None = None) -> Path:
    return (root or project_root()) / ".factory" / "state.db"


def open_store(readonly: bool = False, root: Path | None = None) -> StateStore:
    """Open this project's state store; a missing project is an error that names the fix."""
    path = state_db(root)
    if not path.is_file():
        raise NoProjectError(f"No factory project in {path.parent.parent}. Run `factory init` here first.")
    return StateStore.open(path, readonly=readonly)


def renderer_for(output: str) -> Renderer:
    try:
        return Renderer(OutputMode(output))
    except ValueError:
        raise ConfigError(f"Unknown output mode '{output}'. Use rich, plain or json.") from None


def default_output() -> str:
    """rich on a terminal, plain when piped."""
    return "rich" if sys.stdout.isatty() else "plain"


def latest_run_id(store: StateStore) -> str | None:
    row = store.conn.execute("SELECT run_id FROM runs ORDER BY last_activity DESC, rowid DESC LIMIT 1").fetchone()
    return str(row["run_id"]) if row is not None else None


def resolve_run_id(store: StateStore, run_id: str | None) -> str:
    """The given run id, or the latest run of this project; an error when there is none."""
    chosen = run_id or latest_run_id(store)
    if chosen is None:
        raise ConfigError("This project has no runs yet. Start one with `factory run start`.")
    return chosen


def guard(action: Callable[[], int]) -> int:
    """Run a command body and turn the factory's errors into a message on stderr and an exit code (1 user, 2 environment)."""
    try:
        return action()
    except NoProjectError as err:
        sys.stderr.write(f"error: {err}\n")
        return EXIT_ENV
    except AsfError as err:
        sys.stderr.write(f"error: {err}\n")
        return EXIT_USER
    except KeyboardInterrupt:
        sys.stderr.write("interrupted\n")
        return 130


# -- the registry of projects (name -> directory) kept in the user's data dir ------------------------------------------


def _registry_file() -> Path:
    return get_paths().data_dir / "projects.json"


def load_projects() -> dict[str, str]:
    path = _registry_file()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise ConfigError(f"The project list {path} is not valid JSON ({err}). Fix or delete it.") from err
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def register_project(name: str, root: Path) -> None:
    projects = load_projects()
    projects[name] = str(root.resolve())
    path = _registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(projects, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)


def project_id_for(root: Path) -> str:
    """The registered name of the project at ``root``, or the directory name."""
    resolved = str(root.resolve())
    for name, path in load_projects().items():
        if path == resolved:
            return name
    return root.resolve().name
