# FILE: tests/cli/commands/test_run.py
# ROLE: Tests that prove src/asf/cli/commands/run.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02 Project Input, Run Controls; IF-01; IF-05; D-09 overrides; D-10 switch; D-15; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/commands/run.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/run.py: run_start, run_status, run_pause, run_resume, run_abort, run_cancel_task, register, _pairs (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_run.py` on Windows and Linux once src/asf/cli/commands/run.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_run.py` and `uv run mypy tests/cli/commands/test_run.py` are clean.

import json
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

import asf.cli.commands.run as run_mod
from asf.cli.commands.run import register, run_abort, run_cancel_task, run_pause, run_resume, run_start, run_status


def _commands(project: Any) -> list[tuple[str, str, str | None]]:
    rows = project.store.conn.execute("SELECT command, run_id, task_id FROM commands ORDER BY rowid").fetchall()
    return [(r["command"], r["run_id"], r["task_id"]) for r in rows]


def test_pause_abort_and_cancel_task_write_commands_for_the_supervisor(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    cli_project.add_run()
    assert run_pause("run1") == 0 and run_abort("run1") == 0 and run_cancel_task("run1", "t7") == 0
    assert _commands(cli_project) == [("pause", "run1", None), ("abort", "run1", None), ("cancel_task", "run1", "t7")]
    assert "pause sent" in capsys.readouterr().out


def test_commands_for_an_unknown_run_are_a_user_error(cli_project: Any) -> None:
    with pytest.raises(Exception) as info:  # noqa: PT011 - ConfigError lives in contracts, which this test does not import
        run_pause("ghost")
    assert "Unknown run" in str(info.value)


def test_status_shows_state_cost_tasks_and_waiting_decisions(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    cli_project.add_run(status="PAUSED", cost=1.5, estimated=True)
    cli_project.add_task("t1", state="READY")
    cli_project.add_task("t2", state="READY")
    cli_project.add_task("t3", state="VERIFIED")
    with cli_project.store.conn:
        cli_project.store.conn.execute("INSERT INTO decisions (decision_id, run_id, topic, status, version, payload) VALUES ('d1', 'run1', 'clarify', 'PENDING', 1, '{}')")
    assert run_status(None, "json") == 0
    data = json.loads(capsys.readouterr().out)["data"]
    assert data["status"] == "PAUSED" and data["cost"] == "1.5000 EST" and data["tasks"] == "READY: 2, VERIFIED: 1" and data["decisions waiting"] == 1


def test_status_of_an_unknown_run_is_a_user_error(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    cli_project.add_run()
    assert run_status("ghost", "plain") == 1
    assert "Unknown run" in capsys.readouterr().err


def test_start_without_any_input_names_the_missing_flags(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    assert run_start(None, [], None, None, None, [], []) in (1, 2)
    assert "--input" in capsys.readouterr().err


def test_start_rejects_an_unknown_mode(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    assert run_start("build", [], None, "wizardry", None, [], []) == 1
    assert "Unknown mode" in capsys.readouterr().err


@pytest.mark.parametrize("bad", ["T2", "=x", "T2="])
def test_model_and_strategy_pairs_must_be_role_equals_name(bad: str) -> None:
    with pytest.raises(Exception) as info:  # noqa: PT011
        run_mod._pairs([bad], "--model")
    assert "ROLE=NAME" in str(info.value)
    assert run_mod._pairs(["T2=qwen", "T3 = gpt"], "--model") == {"T2": "qwen", "T3": "gpt"}


def test_start_builds_the_request_runs_intake_then_the_run_and_reports_the_next_step(
    cli_project: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, Any] = {}
    cli_project.add_run("run-xyz", status="AWAITING_DECISION")

    def fake_submit(request: Any, state_store: Any = None, graph: Any = None, **kwargs: Any) -> str:
        seen["request"] = request
        seen["gateway"] = kwargs.get("gateway")
        return "structured"

    def fake_start(structured: Any, root: Path, overrides: dict[str, Any]) -> str:
        seen.update(structured=structured, root=root, overrides=overrides)
        return "run-xyz"

    monkeypatch.setattr(run_mod, "submit", fake_submit)
    monkeypatch.setattr(run_mod, "start_run", fake_start)
    monkeypatch.setattr(run_mod, "_overrides", lambda profile, model, strategy, local: {"gateway": "GW", "profile_name": profile or "hybrid", "allow_local_tests": local})

    assert run_start("Build a todo app", [], None, "new_build", "local-only", ["T2=qwen"], [], True, False) == 0

    assert seen["request"].text == "Build a todo app" and seen["request"].mode_hint.value == "new_build" and seen["request"].project_id == "proj"
    assert seen["structured"] == "structured" and seen["gateway"] == "GW" and seen["root"] == cli_project.root.resolve()
    assert seen["overrides"]["profile_name"] == "local-only" and seen["overrides"]["allow_local_tests"] is True
    assert "factory inbox list" in capsys.readouterr().out


def test_a_failed_run_exits_with_a_user_error_code(cli_project: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    cli_project.add_run("r9", status="FAILED")
    monkeypatch.setattr(run_mod, "submit", lambda *a, **k: "s")
    monkeypatch.setattr(run_mod, "start_run", lambda *a, **k: "r9")
    monkeypatch.setattr(run_mod, "_overrides", lambda *a, **k: {"gateway": None})
    assert run_start("x", [], None, None, None, [], []) == 1


def test_detach_starts_a_background_process_with_the_same_arguments(cli_project: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[tuple[list[str], Path]] = []

    class _Platform:
        def detach(self, argv: list[str], log_path: Path) -> int:
            calls.append((argv, log_path))
            return 4321

    monkeypatch.setattr(run_mod, "get_platform", lambda: _Platform())
    assert run_start("Build it", [], None, "debug", "local-only", ["T2=q"], [], False, True) == 0
    argv, log = calls[0]
    assert argv[1:5] == ["-m", "asf", "run", "start"] and "--detach" not in argv
    assert ["--input", "Build it"] == argv[argv.index("--input") : argv.index("--input") + 2] and "--mode" in argv and "debug" in argv and "T2=q" in argv
    assert log.suffix == ".log" and "4321" in capsys.readouterr().out


def test_resume_continues_the_run_from_its_checkpoint(cli_project: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    cli_project.add_run("run1", status="DONE")
    seen: dict[str, Any] = {}
    monkeypatch.setattr(run_mod, "resume_run", lambda run_id, root, overrides=None: seen.update(run_id=run_id, root=root))
    monkeypatch.setattr(run_mod, "_overrides", lambda *a, **k: {"gateway": None})
    assert run_resume("run1") == 0
    assert seen["run_id"] == "run1" and "report" in capsys.readouterr().out


def test_the_run_group_is_registered(cli_project: Any) -> None:
    app = typer.Typer()
    register(app)
    runner = CliRunner()
    cli_project.add_run()
    assert runner.invoke(app, ["run", "pause", "run1"]).exit_code == 0
    assert runner.invoke(app, ["run", "status", "run1", "--output", "json"]).exit_code == 0
    assert runner.invoke(app, ["run", "cancel-task", "run1", "t1"]).exit_code == 0
