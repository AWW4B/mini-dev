# FILE: tests/cli/commands/test_project.py
# ROLE: Tests that prove src/asf/cli/commands/project.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02 Project History; IF-24; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/commands/project.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/project.py: project_new, project_list, project_show, register (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (adds a run to a project)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_project.py` on Windows and Linux once src/asf/cli/commands/project.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_project.py` and `uv run mypy tests/cli/commands/test_project.py` are clean.

import json
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from asf.cli.commands.project import project_list, project_new, project_show, register


def test_new_creates_the_directory_state_and_registry_entry(fake_paths: Any, tmp_path: Path) -> None:
    target = tmp_path / "work" / "todo"
    assert project_new("todo", target) == 0
    assert (target / ".factory" / "state.db").is_file()
    assert json.loads((fake_paths.data_dir / "projects.json").read_text(encoding="utf-8")) == {"todo": str(target.resolve())}


def test_a_name_cannot_be_reused_for_another_directory(fake_paths: Any, tmp_path: Path) -> None:
    project_new("todo", tmp_path / "a")
    with pytest.raises(Exception) as info:  # noqa: PT011 - ConfigError lives in contracts, which this test does not import
        project_new("todo", tmp_path / "b")
    assert type(info.value).__name__ == "ConfigError" and "already used" in str(info.value)
    assert project_new("todo", tmp_path / "a") == 0  # the same directory is fine


def test_list_shows_projects_with_their_run_counts(fake_paths: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project_new("one", tmp_path / "one")
    project_new("two", tmp_path / "two")
    from asf.m5_shared.state_store.store import StateStore

    store = StateStore.open(tmp_path / "one" / ".factory" / "state.db")
    with store.conn:
        store.conn.execute(
            "INSERT INTO runs (run_id, project_id, status, version, created_at, last_activity, cost, cost_estimated, payload) VALUES ('r1', 'one', 'DONE', 1, 't', 't', 0, 0, '{}')"
        )
    store.close()
    capsys.readouterr()
    assert project_list("json") == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert rows == [{"name": "one", "directory": str((tmp_path / "one").resolve()), "runs": 1}, {"name": "two", "directory": str((tmp_path / "two").resolve()), "runs": 0}]


def test_show_prints_the_project_and_its_recent_runs(fake_paths: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project_new("one", tmp_path / "one")
    capsys.readouterr()
    assert project_show("one", "json") == 0
    out = capsys.readouterr().out.splitlines()
    assert json.loads(out[0])["data"]["name"] == "one" and json.loads(out[1])["title"] == "Recent runs"


def test_show_of_an_unknown_project_is_a_user_error(fake_paths: Any, capsys: pytest.CaptureFixture[str]) -> None:
    assert project_show("ghost", "plain") == 1
    assert "Unknown project" in capsys.readouterr().err


def test_the_project_group_is_registered(fake_paths: Any, tmp_path: Path) -> None:
    app = typer.Typer()
    register(app)
    runner = CliRunner()
    assert runner.invoke(app, ["project", "new", "viacli", str(tmp_path / "x")]).exit_code == 0
    assert "viacli" in runner.invoke(app, ["project", "list", "--output", "plain"]).stdout
    assert [g.name for g in app.registered_groups] == ["project"]
