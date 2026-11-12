# FILE: tests/cli/commands/test_stats.py
# ROLE: Tests that prove src/asf/cli/commands/stats.py meets its DONE WHEN conditions.
# ARCH REF: M1; p10; D-24; D-19 comparability; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/commands/stats.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/stats.py: stats, register (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_stats.py` on Windows and Linux once src/asf/cli/commands/stats.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_stats.py` and `uv run mypy tests/cli/commands/test_stats.py` are clean.

import json
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from asf.cli.commands.stats import register, stats


def _calls(project: Any) -> None:
    project.add_run()
    project.add_call(role="worker", model="coder", tokens_in=1000, tokens_out=200, cost=0.0, strategy="tool_loop")
    project.add_call(role="worker", model="coder", tokens_in=500, tokens_out=100, cost=0.0, strategy="code_exec")
    project.add_call(role="planner", model="gpt", tokens_in=300, tokens_out=300, cost=0.5, estimated=1)


def test_calls_are_grouped_by_role_with_totals(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    _calls(cli_project)
    assert stats(None, "role", "json") == 0
    rows = {r["role"]: r for r in json.loads(capsys.readouterr().out)["rows"]}
    assert rows["worker"]["calls"] == 2 and rows["worker"]["tokens in"] == 1500
    assert rows["planner"]["cost"] == "0.5000 EST"
    assert rows["TOTAL"]["calls"] == 3 and rows["TOTAL"]["tokens out"] == 600


@pytest.mark.parametrize("by", ["model", "provider", "strategy", "task"])
def test_other_groupings_work(cli_project: Any, capsys: pytest.CaptureFixture[str], by: str) -> None:
    _calls(cli_project)
    assert stats("run1", by, "json") == 0
    assert by in json.loads(capsys.readouterr().out)["columns"]


def test_strategies_can_be_compared(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    _calls(cli_project)
    stats(None, "strategy", "json")
    names = [r["strategy"] for r in json.loads(capsys.readouterr().out)["rows"]]
    assert "tool_loop" in names and "code_exec" in names


def test_an_unknown_grouping_is_a_user_error(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    _calls(cli_project)
    assert stats(None, "colour", "plain") == 1
    assert "Cannot group by" in capsys.readouterr().err


def test_a_run_without_calls_still_prints_a_total(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    cli_project.add_run()
    assert stats(None, "role", "json") == 0
    assert json.loads(capsys.readouterr().out)["rows"][-1]["role"] == "TOTAL"


def test_the_stats_command_is_registered(cli_project: Any) -> None:
    app = typer.Typer()
    register(app)
    _calls(cli_project)
    assert CliRunner().invoke(app, ["--by", "model", "--output", "plain"]).exit_code == 0
