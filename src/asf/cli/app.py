# FILE: src/asf/cli/app.py
# ROLE: Root Typer app and the `factory` console-script entry point; bare `factory` opens the main menu on a TTY.
# ARCH REF: M1; p01 HLD; p02; D-11; D-12; D-13; D-40
# OWNS: Root app, global options (--output, --profile), command registration
# DOES NOT OWN: Command behaviour
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/doctor.py: register (command group)
#   - imports from src/asf/cli/commands/init.py: register (command group)
#   - imports from src/asf/cli/commands/project.py: register (command group)
#   - imports from src/asf/cli/commands/run.py: register (command group)
#   - imports from src/asf/cli/commands/trace.py: register (command group)
#   - imports from src/asf/cli/commands/inbox.py: register (command group)
#   - imports from src/asf/cli/commands/dash.py: register (command group)
#   - imports from src/asf/cli/commands/tasks.py: register (command group)
#   - imports from src/asf/cli/commands/history.py: register (command group)
#   - imports from src/asf/cli/commands/report.py: register (command group)
#   - imports from src/asf/cli/commands/models.py: register (command group)
#   - imports from src/asf/cli/commands/skills.py: register (command group)
#   - imports from src/asf/cli/commands/events.py: register (command group)
#   - imports from src/asf/cli/commands/config_cmd.py: register (command group)
#   - imports from src/asf/cli/commands/stats.py: register (command group)
#   - imports from src/asf/cli/commands/mcp.py: register (command group)
#   - imports from src/asf/cli/commands/web.py: register (command group)
#   - imports from src/asf/cli/flows.py: main_menu (bare factory)
#   - imports from src/asf/logging_setup.py: configure_logging (D-26)
#   - called by src/asf/__main__.py: main
#   - called by tests/cli/test_app.py: main
#   - called by pyproject.toml: [project.scripts] factory = "asf.cli.app:main"
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
# DONE WHEN: (1) tests/cli/test_app.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/app.py` and `uv run mypy src/asf/cli/app.py` are clean.

import sys

import typer

import asf.cli.commands.config_cmd as config_cmd
import asf.cli.commands.dash as dash
import asf.cli.commands.doctor as doctor
import asf.cli.commands.events as events
import asf.cli.commands.history as history
import asf.cli.commands.inbox as inbox
import asf.cli.commands.init as init
import asf.cli.commands.mcp as mcp
import asf.cli.commands.models as models
import asf.cli.commands.project as project
import asf.cli.commands.report as report
import asf.cli.commands.run as run
import asf.cli.commands.skills as skills
import asf.cli.commands.stats as stats
import asf.cli.commands.tasks as tasks
import asf.cli.commands.trace as trace
import asf.cli.commands.web as web
from asf.cli.flows import main_menu
from asf.logging_setup import configure_logging

app = typer.Typer(name="factory", no_args_is_help=False, add_completion=False)

_COMMAND_MODULES = (
    doctor,
    init,
    project,
    run,
    trace,
    inbox,
    dash,
    tasks,
    history,
    report,
    models,
    skills,
    events,
    config_cmd,
    stats,
    mcp,
    web,
)
for _mod in _COMMAND_MODULES:
    _mod.register(app)


@app.callback(invoke_without_command=True)
def _root_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        if sys.stdin.isatty() and sys.stdout.isatty():
            raise typer.Exit(code=main_menu())
        raise typer.Exit(code=2)  # nothing to do without a terminal: `factory --help` lists the commands


def main() -> None:
    configure_logging()
    app()
