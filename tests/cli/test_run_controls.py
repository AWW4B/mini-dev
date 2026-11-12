# FILE: tests/cli/test_run_controls.py
# ROLE: Tests that prove src/asf/cli/run_controls.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02 Run Controls; IF-05; D-15; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/run_controls.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/run_controls.py: send_command (unit under test)
#   - imports from src/asf/contracts/control.py: RunCommand (commands to send)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (the command table)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/test_run_controls.py` on Windows and Linux once src/asf/cli/run_controls.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/test_run_controls.py` and `uv run mypy tests/cli/test_run_controls.py` are clean.

from pathlib import Path

import pytest

from asf.cli.run_controls import send_command
from asf.contracts.control import RunCommand
from asf.m5_shared.state_store.store import StateStore


def _project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> StateStore:
    monkeypatch.chdir(tmp_path)
    store = StateStore.open(tmp_path / ".factory" / "state.db")
    with store.conn:
        store.conn.execute(
            "INSERT INTO runs (run_id, project_id, status, version, created_at, last_activity, cost, cost_estimated, payload) "
            "VALUES ('run1', 'p', 'RUNNING', 1, 't', 't', 0, 0, '{}')"
        )
    return store


def test_a_command_row_is_written_for_the_supervisor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _project(tmp_path, monkeypatch)
    command_id = send_command("run1", RunCommand.PAUSE)
    assert command_id.startswith("cmd_")
    (cmd,) = store.poll_commands("run1")
    assert (cmd.command_id, cmd.run_id, cmd.command, cmd.task_id) == (command_id, "run1", RunCommand.PAUSE, None)


def test_each_command_gets_its_own_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _project(tmp_path, monkeypatch)
    assert send_command("run1", RunCommand.PAUSE) != send_command("run1", RunCommand.PAUSE)


def test_cancel_task_carries_its_task_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _project(tmp_path, monkeypatch)
    send_command("run1", RunCommand.CANCEL_TASK, "task-7")
    (cmd,) = store.poll_commands("run1")
    assert cmd.task_id == "task-7"


def test_cancel_task_without_a_task_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _project(tmp_path, monkeypatch)
    with pytest.raises(Exception) as info:  # noqa: PT011 - ConfigError lives in contracts, which this test does not import
        send_command("run1", RunCommand.CANCEL_TASK)
    assert type(info.value).__name__ == "ConfigError"


def test_an_unknown_run_is_refused_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _project(tmp_path, monkeypatch)
    with pytest.raises(Exception) as info:  # noqa: PT011
        send_command("ghost", RunCommand.ABORT)
    assert "Unknown run" in str(info.value)
    assert store.conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0] == 0


def test_outside_a_project_the_error_says_how_to_start_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(Exception) as info:  # noqa: PT011
        send_command("run1", RunCommand.PAUSE)
    assert "factory init" in str(info.value)
