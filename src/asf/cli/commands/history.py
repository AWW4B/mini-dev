# FILE: src/asf/cli/commands/history.py
# ROLE: Implements `factory history list|show`.
# ARCH REF: M1; p02 Project History; IF-24
# OWNS: Argument parsing and output for this command group
# DOES NOT OWN: Business logic (lives in the imported modules)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (read-only queries / command rows)
#   - imports from src/asf/contracts/history.py: HistoryQuery (IF-24)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: EXIT_OK, EXIT_USER, guard, open_store, renderer_for (shared CLI plumbing)
#   - called by src/asf/cli/app.py: register
#   - called by tests/cli/commands/test_history.py: history_list, history_show, register
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Never run agents or keep execution state in the CLI; write commands to the command table (IF-05) and read state/events (M1 is a thin client).
#   6. Support --output rich|plain|json through Renderer; prompts only when stdin and stdout are TTYs, otherwise exit 2 naming the missing flags (D-13).
#   7. Exit codes: 0 success, 1 user/validation error, 2 environment problem.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/cli/commands/test_history.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/commands/history.py` and `uv run mypy src/asf/cli/commands/history.py` are clean.

import typer

from asf.cli.context import EXIT_OK, EXIT_USER, guard, open_store, renderer_for
from asf.contracts.history import HistoryQuery
from asf.m5_shared.state_store.store import StateStore


def history_list(project: str | None, output: str = "rich") -> int:
    store = open_store(readonly=True)
    try:
        result = store.history(HistoryQuery.model_validate({"project_id": project, "limit": 50}))
    finally:
        store.close()
    renderer_for(output).table(
        "Runs", ["run", "project", "status", "last activity", "cost"],
        [[r.run_id, r.project_id, r.status, r.last_activity, f"{r.cost:.4f}{' EST' if r.cost_estimated else ''}"] for r in result.runs],
    )
    return EXIT_OK


def _decisions(store: StateStore, run_id: str) -> int:
    return int(store.conn.execute("SELECT COUNT(*) FROM decisions WHERE run_id = ?", (run_id,)).fetchone()[0])


def history_show(run_id: str, output: str = "rich") -> int:
    renderer = renderer_for(output)
    store = open_store(readonly=True)
    try:
        result = store.history(HistoryQuery.model_validate({"run_id": run_id, "limit": 1}))
        if not result.runs:
            renderer.message(f"Unknown run '{run_id}'. `factory history list` shows the runs of this project.", "error")
            return EXIT_USER
        run = result.runs[0]
        tasks = {str(r["state"]): int(r["n"]) for r in store.conn.execute("SELECT state, COUNT(*) AS n FROM tasks WHERE run_id = ? GROUP BY state", (run_id,))}
        events = int(store.conn.execute("SELECT COUNT(*) FROM events WHERE run_id = ?", (run_id,)).fetchone()[0])
        decisions = _decisions(store, run_id)
    finally:
        store.close()
    renderer.record(
        f"Run {run.run_id}",
        {
            "project": run.project_id, "status": run.status, "last activity": run.last_activity,
            "cost": f"{run.cost:.4f}{' EST' if run.cost_estimated else ''}", "tasks": ", ".join(f"{s}: {n}" for s, n in sorted(tasks.items())) or "none",
            "events": events, "decisions": decisions,
        },
    )
    return EXIT_OK


def register(app: typer.Typer) -> None:
    """Attach the `history` command(s) to the root Typer app."""
    group = typer.Typer(help="Past runs of this project.", no_args_is_help=True)

    @group.command("list")
    def list_cmd(project: str | None = typer.Option(None, "--project"), output: str = typer.Option("rich", "--output", "-o")) -> None:
        raise typer.Exit(code=guard(lambda: history_list(project, output)))

    @group.command("show")
    def show_cmd(run_id: str, output: str = typer.Option("rich", "--output", "-o")) -> None:
        raise typer.Exit(code=guard(lambda: history_show(run_id, output)))

    app.add_typer(group, name="history")
