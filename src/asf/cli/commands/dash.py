# FILE: src/asf/cli/commands/dash.py
# ROLE: Implements `factory dash`: live resource dashboard.
# ARCH REF: M1; p02 Resource Dashboard; IF-19
# OWNS: Argument parsing and output for this command group
# DOES NOT OWN: Business logic (lives in the imported modules)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/views/dash_view.py: DashView (rendering)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: EXIT_OK, default_output, guard, renderer_for (shared CLI plumbing)
#   - called by src/asf/cli/app.py: register
#   - called by tests/cli/commands/test_dash.py: dash, register
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
# DONE WHEN: (1) tests/cli/commands/test_dash.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/commands/dash.py` and `uv run mypy src/asf/cli/commands/dash.py` are clean.

import typer

from asf.cli.context import EXIT_OK, default_output, guard, renderer_for
from asf.cli.views.dash_view import DashView


def dash(run_id: str | None) -> int:
    """The live dashboard on a terminal (Ctrl+C only closes the view); a single snapshot when piped."""
    view = DashView(renderer_for(default_output()), run_id)
    if default_output() == "rich":
        view.live()
    else:
        view.render_once()
    return EXIT_OK


def register(app: typer.Typer) -> None:
    """Attach the `dash` command(s) to the root Typer app."""

    @app.command("dash", help="Live dashboard: status, queue, tokens, cost.")
    def dash_cmd(run_id: str | None = typer.Argument(None)) -> None:
        raise typer.Exit(code=guard(lambda: dash(run_id)))
