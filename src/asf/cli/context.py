# FILE: src/asf/cli/context.py
# ROLE: Resolves the current project, opens its state store and renders output: the small shared plumbing of the CLI commands.
# ARCH REF: M1; p02; D-13; D-15
# OWNS: Project root, store opening, exit codes, run id defaults
# DOES NOT OWN: Command behaviour (commands/*.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (output modes)
#   - imports from src/asf/contracts/errors.py: ConfigError (no project, bad output mode)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (the project's state.db)
#   - called by tests/cli/test_context.py: EXIT_OK, EXIT_USER, EXIT_ENV, project_root, state_db, open_store, renderer_for, latest_run_id, resolve_run_id
#   - called by src/asf/cli/run_controls.py: open_store
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/cli/test_context.py pass on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/context.py` and `uv run mypy src/asf/cli/context.py` are clean.

from pathlib import Path

from asf.cli.ui.render import OutputMode, Renderer
from asf.contracts.errors import ConfigError
from asf.m5_shared.state_store.store import StateStore

EXIT_OK = 0
EXIT_USER = 1  # the user's input was wrong
EXIT_ENV = 2  # the environment is the problem (no project, missing extra, no terminal)


def project_root() -> Path:
    """The project is the current directory, as with git: its state lives in ./.factory/."""
    return Path.cwd().resolve()


def state_db(root: Path | None = None) -> Path:
    return (root or project_root()) / ".factory" / "state.db"


def open_store(readonly: bool = False, root: Path | None = None) -> StateStore:
    """Open this project's state store; a missing project is a ConfigError that names the fix."""
    path = state_db(root)
    if not path.is_file():
        raise ConfigError(f"No factory project in {path.parent.parent}. Run `factory init` here first.")
    return StateStore.open(path, readonly=readonly)


def renderer_for(output: str) -> Renderer:
    try:
        return Renderer(OutputMode(output))
    except ValueError:
        raise ConfigError(f"Unknown output mode '{output}'. Use rich, plain or json.") from None


def latest_run_id(store: StateStore) -> str | None:
    row = store.conn.execute("SELECT run_id FROM runs ORDER BY last_activity DESC, rowid DESC LIMIT 1").fetchone()
    return str(row["run_id"]) if row is not None else None


def resolve_run_id(store: StateStore, run_id: str | None) -> str:
    """The given run id, or the latest run of this project; ConfigError when there is none."""
    chosen = run_id or latest_run_id(store)
    if chosen is None:
        raise ConfigError("This project has no runs yet. Start one with `factory run start`.")
    return chosen
