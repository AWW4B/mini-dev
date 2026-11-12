# FILE: tests/cli/commands/test_history.py
# ROLE: Tests that prove src/asf/cli/commands/history.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02 Project History; IF-24; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/commands/history.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/history.py: history_list, history_show, register (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_history.py` on Windows and Linux once src/asf/cli/commands/history.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_history.py` and `uv run mypy tests/cli/commands/test_history.py` are clean.

import json
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from asf.cli.commands.history import history_list, history_show, register


def test_list_shows_runs_newest_first_with_estimated_costs_flagged(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    cli_project.add_run("old", status="DONE", cost=1.0, activity="2026-01-01")
    cli_project.add_run("new", status="RUNNING", cost=2.5, estimated=True, activity="2026-06-01")
    assert history_list(None, "json") == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [r["run"] for r in rows] == ["new", "old"] and rows[0]["cost"] == "2.5000 EST" and rows[1]["cost"] == "1.0000"


def test_list_can_be_limited_to_a_project(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    cli_project.add_run("r1")
    assert history_list("other-project", "json") == 0
    assert json.loads(capsys.readouterr().out)["rows"] == []


def test_show_summarises_tasks_events_and_decisions(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    cli_project.add_run("r1", status="DONE", cost=0.5)
    cli_project.add_task("t1", state="VERIFIED", run_id="r1")
    cli_project.add_task("t2", state="VERIFIED", run_id="r1")
    assert history_show("r1", "json") == 0
    data = json.loads(capsys.readouterr().out)["data"]
    assert data["status"] == "DONE" and data["tasks"] == "VERIFIED: 2" and data["events"] == 0 and data["decisions"] == 0


def test_show_of_an_unknown_run_is_a_user_error(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    assert history_show("ghost", "plain") == 1
    assert "Unknown run" in capsys.readouterr().err


def test_the_history_group_is_registered(cli_project: Any) -> None:
    app = typer.Typer()
    register(app)
    assert CliRunner().invoke(app, ["history", "list", "--output", "plain"]).exit_code == 0
