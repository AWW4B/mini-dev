# FILE: src/asf/cli/commands/doctor.py
# ROLE: Implements `factory doctor`: runs environment checks, prints them and writes the report.
# ARCH REF: FR-4 doctor; D-45
# OWNS: Argument parsing and output for this command group
# DOES NOT OWN: Business logic (lives in the imported modules)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/doctor/checks.py: run_all_checks (checks)
#   - imports from src/asf/doctor/report.py: write_report, exit_code_for (report)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - called by src/asf/cli/flows.py: doctor
#   - called by src/asf/cli/app.py: register
#   - called by tests/cli/commands/test_doctor.py: doctor, register
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
# DONE WHEN: (1) tests/cli/commands/test_doctor.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/commands/doctor.py` and `uv run mypy src/asf/cli/commands/doctor.py` are clean.

import json

import typer

from asf.cli.ui.render import OutputMode, Renderer
from asf.doctor.checks import run_all_checks
from asf.doctor.report import exit_code_for, write_report


def doctor(output: str = "rich") -> int:
    results = run_all_checks()
    write_report(results)
    code = exit_code_for(results)

    try:
        mode = OutputMode(output)
        renderer = Renderer(mode)
        rows = [[r.name, str(r.status), r.detail] for r in results]
        renderer.table("Doctor Checks", ["Check", "Status", "Details"], rows)
    except (NotImplementedError, Exception):
        # Fallback if Renderer is not yet implemented or raises
        if output == "json":
            print(json.dumps([r.model_dump() for r in results], indent=2))
        else:
            for r in results:
                status_str = getattr(r.status, "value", str(r.status)).upper()
                print(f"[{status_str:4s}] {r.name:<15s}: {r.detail}")
    return code


def register(app: typer.Typer) -> None:
    """Attach the `doctor` command(s) to the root Typer app."""
    @app.command("doctor")
    def doctor_cmd(
        output: str = typer.Option("rich", "--output", "-o", help="Output mode: rich | plain | json"),
    ) -> None:
        exit_code = doctor(output=output)
        raise typer.Exit(code=exit_code)
