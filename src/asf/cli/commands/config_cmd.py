# FILE: src/asf/cli/commands/config_cmd.py
# ROLE: Implements `factory config show|validate`.
# ARCH REF: M1; D-37
# OWNS: Argument parsing and output for this command group
# DOES NOT OWN: Business logic (lives in the imported modules)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/settings.py: load_settings (settings)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: EXIT_OK, EXIT_USER, guard, project_root, renderer_for (shared CLI plumbing)
#   - called by src/asf/cli/app.py: register
#   - called by tests/cli/commands/test_config_cmd.py: config_show, config_validate, register
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
# DONE WHEN: (1) tests/cli/commands/test_config_cmd.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/commands/config_cmd.py` and `uv run mypy src/asf/cli/commands/config_cmd.py` are clean.

import typer

from asf.cli.context import EXIT_OK, EXIT_USER, guard, project_root, renderer_for
from asf.config.settings import load_settings


def config_show(output: str = "rich") -> int:
    """The effective settings: packaged defaults, user file, project file, FACTORY_* variables."""
    settings = load_settings(project_root())
    data = settings.model_dump()
    flat = {k: (", ".join(f"{a}={b}" for a, b in v.items()) if isinstance(v, dict) else v) for k, v in data.items()}
    renderer_for(output).record("Effective settings", flat)
    return EXIT_OK


def config_validate() -> int:
    try:
        load_settings(project_root())
    except Exception as err:  # noqa: BLE001 - pydantic and the loader raise different types; all mean "invalid"
        renderer_for("plain").message(f"The configuration is invalid: {err}", "error")
        return EXIT_USER
    renderer_for("plain").message("The configuration is valid.", "success")
    return EXIT_OK


def register(app: typer.Typer) -> None:
    """Attach the `config` command(s) to the root Typer app."""
    group = typer.Typer(help="Show and check the configuration.", no_args_is_help=True)

    @group.command("show")
    def show_cmd(output: str = typer.Option("rich", "--output", "-o")) -> None:
        raise typer.Exit(code=guard(lambda: config_show(output)))

    @group.command("validate")
    def validate_cmd() -> None:
        raise typer.Exit(code=guard(config_validate))

    app.add_typer(group, name="config")
