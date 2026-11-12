# FILE: src/asf/cli/commands/project.py
# ROLE: Implements `factory project new|list|show`.
# ARCH REF: M1; p02 Project History; IF-24
# OWNS: Argument parsing and output for this command group
# DOES NOT OWN: Business logic (lives in the imported modules)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (read-only queries / command rows)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: EXIT_OK, EXIT_USER, guard, load_projects, register_project, renderer_for, state_db (shared CLI plumbing)
#   - imports from src/asf/contracts/errors.py: ConfigError (a name already in use)
#   - imports from src/asf/contracts/history.py: HistoryQuery (recent runs)
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

from asf.cli.context import EXIT_OK, EXIT_USER, guard, load_projects, register_project, renderer_for, state_db
from asf.contracts.errors import ConfigError
from asf.contracts.history import HistoryQuery
from asf.m5_shared.state_store.store import StateStore


def project_new(name: str, path: Path) -> int:
    """Create a project directory with its state store and register it under ``name``."""
    root = path.resolve()
    if name in load_projects() and load_projects()[name] != str(root):
        raise ConfigError(f"The name '{name}' is already used by {load_projects()[name]}.")
    (root / ".factory").mkdir(parents=True, exist_ok=True)
    StateStore.open(state_db(root)).close()
    ignore = root / ".factory" / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")
    register_project(name, root)
    renderer_for("plain").message(f"Project '{name}' created in {root}", "success")
    return EXIT_OK


def _runs_of(root: str) -> int:
    db = state_db(Path(root))
    if not db.is_file():
        return 0
    store = StateStore.open(db, readonly=True)
    try:
        return int(store.conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0])
    finally:
        store.close()


def project_list(output: str = "rich") -> int:
    renderer = renderer_for(output)
    projects = load_projects()
    renderer.table("Projects", ["name", "directory", "runs"], [[n, p, _runs_of(p)] for n, p in sorted(projects.items())])
    return EXIT_OK


def project_show(project: str, output: str = "rich") -> int:
    renderer = renderer_for(output)
    projects = load_projects()
    root = projects.get(project)
    if root is None:
        renderer.message(f"Unknown project '{project}'. `factory project list` shows the known ones.", "error")
        return EXIT_USER
    db = state_db(Path(root))
    renderer.record("Project", {"name": project, "directory": root, "state": "ready" if db.is_file() else "no state database yet (run `factory init` there)"})
    if db.is_file():
        store = StateStore.open(db, readonly=True)
        try:
            history = store.history(HistoryQuery.model_validate({"project_id": project, "limit": 10}))
        finally:
            store.close()
        renderer.table(
            "Recent runs",
            ["run", "status", "last activity", "cost"],
            [[r.run_id, r.status, r.last_activity, f"{r.cost:.4f}{' EST' if r.cost_estimated else ''}"] for r in history.runs],
        )
    return EXIT_OK


def register(app: typer.Typer) -> None:
    """Attach the `project` command(s) to the root Typer app."""
    group = typer.Typer(help="Create and inspect projects.", no_args_is_help=True)

    @group.command("new")
    def new_cmd(name: str, path: Path = typer.Argument(None, help="Directory (default: ./NAME)")) -> None:
        raise typer.Exit(code=guard(lambda: project_new(name, path or Path.cwd() / name)))

    @group.command("list")
    def list_cmd(output: str = typer.Option("rich", "--output", "-o")) -> None:
        raise typer.Exit(code=guard(lambda: project_list(output)))

    @group.command("show")
    def show_cmd(project: str, output: str = typer.Option("rich", "--output", "-o")) -> None:
        raise typer.Exit(code=guard(lambda: project_show(project, output)))

    app.add_typer(group, name="project")
