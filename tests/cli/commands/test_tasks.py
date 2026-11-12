# FILE: tests/cli/commands/test_tasks.py
# ROLE: Tests that prove src/asf/cli/commands/tasks.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02; p06 states; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/commands/tasks.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/tasks.py: tasks_tree, tasks_show, register (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_tasks.py` on Windows and Linux once src/asf/cli/commands/tasks.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_tasks.py` and `uv run mypy tests/cli/commands/test_tasks.py` are clean.

import json
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from asf.cli.commands.tasks import register, tasks_show, tasks_tree


def test_tree_prints_the_hierarchy(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    cli_project.add_run()
    cli_project.add_task("root", state="DECOMPOSED")
    cli_project.add_task("a", parent="root", state="RUNNING", attempts=1)
    assert tasks_tree("run1", "json") == 0
    (root,) = json.loads(capsys.readouterr().out)["nodes"]
    assert root["state"] == "DECOMPOSED" and root["children"][0]["state"] == "RUNNING"


def test_tree_defaults_to_the_latest_run(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    cli_project.add_run("run1")
    cli_project.add_task("t1")
    assert tasks_tree("", "plain") == 0
    assert "t1: goal of t1" in capsys.readouterr().out


def test_show_prints_every_field_of_a_task_and_its_attempts(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    cli_project.add_run()
    cli_project.add_task("t1", state="FAILED_ATTEMPT", attempts=2)
    with cli_project.store.conn:
        cli_project.store.conn.execute("INSERT INTO attempts (attempt_id, task_id, run_id, status) VALUES ('a1', 't1', 'run1', 'FAILED')")
    assert tasks_show("t1", "json") == 0
    data = json.loads(capsys.readouterr().out)["data"]
    assert data["state"] == "FAILED_ATTEMPT" and data["goal"] == "goal of t1" and data["counters"] == "attempts=2"
    assert data["files"] == "src/t1.py" and data["attempts"] == "a1 (FAILED)"


def test_show_of_an_unknown_task_is_a_user_error(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    assert tasks_show("ghost", "plain") == 1
    assert "Unknown task" in capsys.readouterr().err


def test_the_tasks_group_is_registered(cli_project: Any) -> None:
    app = typer.Typer()
    register(app)
    cli_project.add_run()
    cli_project.add_task("t1")
    assert CliRunner().invoke(app, ["tasks", "tree", "run1", "--output", "plain"]).exit_code == 0
    assert CliRunner().invoke(app, ["tasks", "show", "t1", "--output", "plain"]).exit_code == 0
