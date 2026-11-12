# FILE: tests/cli/commands/test_trace.py
# ROLE: Tests that prove src/asf/cli/commands/trace.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02 Active Group Chat (terminal view); IF-18; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/commands/trace.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/trace.py: trace, register (unit under test)
#   - imports from src/asf/contracts/events.py: EventEnvelope (event fixtures)
#   - imports from src/asf/m5_shared/events/event_log.py: EventLog (stores the events)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_trace.py` on Windows and Linux once src/asf/cli/commands/trace.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_trace.py` and `uv run mypy tests/cli/commands/test_trace.py` are clean.

from datetime import UTC, datetime
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

import asf.cli.commands.trace as trace_mod
from asf.cli.commands.trace import register, trace
from asf.contracts.events import EventEnvelope
from asf.m5_shared.events.event_log import EventLog


def _log(project: Any) -> EventLog:
    project.add_run()
    log = EventLog(project.store.conn)
    log.append(
        [
            EventEnvelope.model_validate(
                {
                    "event_id": f"e{i}", "run_id": "run1", "seq": 0, "ts": datetime(2026, 11, 12, 10, 0, i, tzinfo=UTC),
                    "actor": {"kind": "agent", "role": "worker", "name": "Worker"}, "kind": kind, "correlation_id": "c", "visibility": vis, "payload": {},
                }
            )
            for i, (kind, vis) in enumerate([("task_received", "user"), ("usage", "internal"), ("gate_result", "user")], start=1)
        ]
    )
    return log


def test_trace_prints_the_user_level_events(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    _log(cli_project)
    assert trace(None) == 0
    out = capsys.readouterr().out
    assert "task_received" in out and "gate_result" in out and "usage" not in out


def test_the_internal_level_shows_everything(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    _log(cli_project)
    trace("run1", level="internal")
    assert "usage" in capsys.readouterr().out


def test_an_unknown_level_is_a_user_error(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    _log(cli_project)
    assert trace(None, level="debug") == 1
    assert "--level" in capsys.readouterr().err


def test_follow_keeps_the_view_open_until_it_is_closed(cli_project: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _log(cli_project)
    closed: list[bool] = []

    class _Live:
        def __init__(self, renderer: Any, run_id: str | None, level: str = "user", task: str | None = None) -> None:
            pass

        def render_once(self) -> int:
            return 0

        def live(self) -> None:
            closed.append(True)

    monkeypatch.setattr(trace_mod, "TraceView", _Live)
    assert trace(None, follow=True) == 0 and closed == [True]


def test_the_trace_command_is_registered(cli_project: Any) -> None:
    app = typer.Typer()
    register(app)
    _log(cli_project)
    assert CliRunner().invoke(app, ["run1", "--level", "internal"]).exit_code == 0
