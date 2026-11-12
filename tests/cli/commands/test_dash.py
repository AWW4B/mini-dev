# FILE: tests/cli/commands/test_dash.py
# ROLE: Tests that prove src/asf/cli/commands/dash.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02 Resource Dashboard; IF-19; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/commands/dash.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/dash.py: dash, register (unit under test)
#   - imports from tests/conftest.py: cli_project (a project directory with a real store)
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use the tmp_path fixture or the fake_paths fixture for every filesystem location.
#   6. Use the fakes from tests/conftest.py instead of real GPUs, networks, sandboxes or model providers unless the test is marked needs_gpu, needs_network or needs_sandbox.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; real API keys; network access in unmarked tests; sleeping for timing (use the fake clock)
# ERRORS: Failures surface as pytest assertion failures.
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_dash.py` on Windows and Linux once src/asf/cli/commands/dash.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_dash.py` and `uv run mypy tests/cli/commands/test_dash.py` are clean.

from typing import Any

import pytest
import typer
from typer.testing import CliRunner

import asf.cli.commands.dash as dash_mod
from asf.cli.commands.dash import dash, register


def test_piped_output_is_a_single_snapshot(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    cli_project.add_run(status="RUNNING", cost=0.25)
    cli_project.add_task("t1", state="READY")
    assert dash(None) == 0
    out = capsys.readouterr().out
    assert "Run run1" in out and "RUNNING" in out and "READY" in out


def test_on_a_terminal_the_live_view_is_used(cli_project: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class _View:
        def __init__(self, renderer: Any, run_id: str | None) -> None:
            pass

        def live(self) -> None:
            calls.append("live")

        def render_once(self) -> None:
            calls.append("once")

    monkeypatch.setattr(dash_mod, "DashView", _View)
    monkeypatch.setattr(dash_mod, "default_output", lambda: "rich")
    assert dash("run1") == 0 and calls == ["live"]


def test_no_runs_is_a_clear_error(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    app = typer.Typer()
    register(app)
    result = CliRunner().invoke(app, [])
    assert result.exit_code == 1 and "no runs yet" in result.stderr
