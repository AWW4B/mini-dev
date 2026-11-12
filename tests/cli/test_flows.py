# FILE: tests/cli/test_flows.py
# ROLE: Tests that prove src/asf/cli/flows.py meets its DONE WHEN conditions.
# ARCH REF: M1; D-12 guided flows; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/flows.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/flows.py: flow_new_run, flow_resume, flow_inbox_answer, flow_models_setup, flow_doctor, main_menu (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/test_flows.py` on Windows and Linux once src/asf/cli/flows.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/test_flows.py` and `uv run mypy tests/cli/test_flows.py` are clean.

import json
from pathlib import Path
from typing import Any

import pytest

import asf.cli.flows as flows
from asf.cli.flows import flow_doctor, flow_inbox_answer, flow_models_setup, flow_new_run, flow_resume, main_menu


class _Script:
    """Replays prompt answers in order and records every question asked."""

    def __init__(self, *answers: Any) -> None:
        self.answers = list(answers)
        self.asked: list[str] = []

    def __call__(self, prompt: str, *args: Any, **kwargs: Any) -> Any:
        self.asked.append(prompt)
        return self.answers.pop(0)


def _returning(log: list[Any], code: int) -> Any:
    """A stand-in command that records its arguments (one value, or a tuple for several) and returns an exit code."""

    def call(*args: Any) -> int:
        log.append(args[0] if len(args) == 1 else args)
        return code

    return call


def _returning_label(log: list[str], label: str, code: int) -> Any:
    def call(*args: Any) -> int:
        log.append(label)
        return code

    return call


def _tty(monkeypatch: pytest.MonkeyPatch, value: bool = True) -> None:
    monkeypatch.setattr(flows, "is_interactive", lambda: value)


def test_every_flow_that_prompts_refuses_to_run_without_a_terminal(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _tty(monkeypatch, False)
    for flow in (flow_new_run, flow_resume, flow_inbox_answer, flow_models_setup):
        assert flow() == 2
    assert "needs a terminal" in capsys.readouterr().out


def test_new_run_asks_the_questions_then_calls_run_start(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _tty(monkeypatch)
    seen: dict[str, Any] = {}
    monkeypatch.setattr(flows, "ask_text", _Script("Build a todo app", f'"{tmp_path / "spec.md"}", ', "", ))
    monkeypatch.setattr(flows, "choose", _Script("feature"))
    monkeypatch.setattr(flows, "confirm", _Script(True, True))
    monkeypatch.setattr(flows, "run_start", lambda *args: seen.update(args=args) or 0)

    assert flow_new_run() == 0
    text, files, repo, mode, profile, model, strategy, local_tests, detach = seen["args"]
    assert text == "Build a todo app" and files == [tmp_path / "spec.md"] and repo is None and mode == "feature"
    assert (profile, model, strategy, local_tests, detach) == (None, [], [], True, False)


def test_new_run_can_be_cancelled_at_the_last_question(monkeypatch: pytest.MonkeyPatch) -> None:
    _tty(monkeypatch)
    monkeypatch.setattr(flows, "ask_text", _Script("x", "", ""))
    monkeypatch.setattr(flows, "choose", _Script("(let the factory decide)"))
    monkeypatch.setattr(flows, "confirm", _Script(False, False))
    monkeypatch.setattr(flows, "run_start", lambda *args: pytest.fail("the run must not start"))
    assert flow_new_run() == 0


def test_resume_offers_the_waiting_runs(cli_project: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _tty(monkeypatch)
    assert flow_resume() == 0 and "No run is waiting" in capsys.readouterr().out
    cli_project.add_run("run-a", status="PAUSED")
    cli_project.add_run("run-b", status="DONE")
    seen: list[str] = []
    picker = _Script("run-a  [PAUSED]")
    monkeypatch.setattr(flows, "choose", picker)
    monkeypatch.setattr(flows, "run_resume", _returning(seen, 0))
    assert flow_resume() == 0 and seen == ["run-a"]


def test_inbox_answer_picks_the_decision_and_option_then_offers_to_continue(cli_project: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _tty(monkeypatch)
    payload = {"decision_id": "d1", "run_id": "run1", "kind": "clarify", "requester": "m", "question": "Which database should we use?", "options": ["sqlite", "postgres"]}
    with cli_project.store.conn:
        cli_project.store.conn.execute("INSERT INTO decisions (decision_id, run_id, topic, status, version, payload) VALUES ('d1', 'run1', 'clarify', 'PENDING', 1, ?)", (json.dumps(payload),))
    answered: list[tuple[str, Any, Any]] = []
    resumed: list[str] = []
    monkeypatch.setattr(flows, "choose", _Script("d1: Which database should we use?", "sqlite"))
    monkeypatch.setattr(flows, "ask_text", _Script("because it is simple"))
    monkeypatch.setattr(flows, "confirm", _Script(True))
    monkeypatch.setattr(flows, "inbox_answer", _returning(answered, 0))
    monkeypatch.setattr(flows, "run_resume", _returning(resumed, 0))
    assert flow_inbox_answer() == 0
    assert answered == [("d1", "sqlite", "because it is simple")] and resumed == ["run1"]


def test_inbox_answer_with_nothing_waiting(cli_project: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _tty(monkeypatch)
    assert flow_inbox_answer() == 0 and "No decisions are waiting" in capsys.readouterr().out


def test_models_setup_runs_init_then_optionally_the_doctor(monkeypatch: pytest.MonkeyPatch) -> None:
    _tty(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(flows, "models_init", _returning_label(calls, "init", 0))
    monkeypatch.setattr(flows, "doctor", _returning_label(calls, "doctor", 0))
    monkeypatch.setattr(flows, "confirm", _Script(True))
    assert flow_models_setup() == 0 and calls == ["init", "doctor"]


def test_doctor_flow_calls_the_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flows, "doctor", lambda output: 1)
    assert flow_doctor() == 1


def test_main_menu_loops_until_quit_and_runs_the_chosen_flow(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _tty(monkeypatch)
    monkeypatch.setattr(flows, "choose", _Script("Check the environment", "Start a new run", "Quit"))
    monkeypatch.setattr(flows, "flow_doctor", lambda: 0)
    monkeypatch.setattr(flows, "flow_new_run", lambda: 1)
    assert main_menu() == 0
    assert "finished with exit code 1" in capsys.readouterr().out


def test_main_menu_without_a_terminal_points_at_help(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _tty(monkeypatch, False)
    assert main_menu() == 1 and "factory --help" in capsys.readouterr().out
