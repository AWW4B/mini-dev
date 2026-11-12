# FILE: src/asf/cli/commands/skills.py
# ROLE: Implements `factory skills list|validate`.
# ARCH REF: M1; p12; D-17; IF-23
# OWNS: Argument parsing and output for this command group
# DOES NOT OWN: Business logic (lives in the imported modules)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/tools/skills.py: SkillsRegistry (IF-23)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: EXIT_OK, EXIT_USER, guard, renderer_for (shared CLI plumbing)
#   - called by src/asf/cli/app.py: register
#   - called by tests/cli/commands/test_skills.py: skills_list, skills_validate, register
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
# DONE WHEN: (1) tests/cli/commands/test_skills.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/commands/skills.py` and `uv run mypy src/asf/cli/commands/skills.py` are clean.

import typer

from asf.cli.context import EXIT_OK, EXIT_USER, guard, renderer_for
from asf.m5_shared.tools.skills import SkillsRegistry


def skills_list(output: str = "rich") -> int:
    registry = SkillsRegistry()
    manifests = sorted(registry.lookup("", "*"), key=lambda m: m.name)
    renderer_for(output).table(
        "Agent Skills", ["name", "version", "tools", "size", "description"],
        [[m.name, m.version, ", ".join(m.allowed_tools) or "-", f"{m.body_chars} chars", m.description] for m in manifests],
    )
    return EXIT_OK


def skills_validate() -> int:
    problems = SkillsRegistry().validate_all()
    renderer = renderer_for("plain")
    if problems:
        for problem in problems:
            renderer.message(problem, "warning")
        return EXIT_USER
    renderer.message("All skills are valid.", "success")
    return EXIT_OK


def register(app: typer.Typer) -> None:
    """Attach the `skills` command(s) to the root Typer app."""
    group = typer.Typer(help="List and validate Agent Skills.", no_args_is_help=True)

    @group.command("list")
    def list_cmd(output: str = typer.Option("rich", "--output", "-o")) -> None:
        raise typer.Exit(code=guard(lambda: skills_list(output)))

    @group.command("validate")
    def validate_cmd() -> None:
        raise typer.Exit(code=guard(skills_validate))

    app.add_typer(group, name="skills")
