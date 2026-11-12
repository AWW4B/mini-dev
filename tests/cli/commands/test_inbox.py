# FILE: tests/cli/commands/test_inbox.py
# ROLE: Tests that prove src/asf/cli/commands/inbox.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02 Decision Inbox; IF-03; IF-04; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/commands/inbox.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/inbox.py: inbox_list, inbox_show, inbox_answer, register (unit under test)
#   - imports from src/asf/contracts/decisions.py: DecisionRequest (request fixtures)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (writes the pending decisions)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_inbox.py` on Windows and Linux once src/asf/cli/commands/inbox.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_inbox.py` and `uv run mypy tests/cli/commands/test_inbox.py` are clean.

import json
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from asf.cli.commands.inbox import inbox_answer, inbox_list, inbox_show, register
from asf.contracts.decisions import DecisionRequest
from asf.m5_shared.decisions.broker import DecisionBroker


def _ask(project: Any, decision_id: str = "d1", options: list[str] | None = None, run_id: str = "run1") -> None:
    DecisionBroker(project.store).request(
        DecisionRequest.model_validate(
            {
                "decision_id": decision_id, "run_id": run_id, "kind": "clarify", "requester": "m2", "question": f"Question {decision_id}?",
                "options": options if options is not None else ["yes", "no"], "default_on_timeout": None,
            }
        )
    )


def test_list_shows_what_is_waiting(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    _ask(cli_project)
    assert inbox_list(None, "json") == 0
    assert json.loads(capsys.readouterr().out)["rows"][0]["id"] == "d1"


def test_show_prints_the_card_and_unknown_cards_are_errors(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    _ask(cli_project)
    assert inbox_show("d1") == 0
    assert "Question d1?" in capsys.readouterr().out
    assert inbox_show("nope") == 1 and "No pending decision" in capsys.readouterr().err


def test_answer_resolves_the_decision_and_says_how_to_continue(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    _ask(cli_project)
    assert inbox_answer("d1", "yes", "because") == 0
    row = cli_project.store.conn.execute("SELECT status, payload FROM decisions WHERE decision_id = 'd1'").fetchone()
    assert row["status"] == "RESOLVED" and json.loads(row["payload"])["resolution"]["text"] == "because"
    assert "factory run resume run1" in capsys.readouterr().out
    assert inbox_answer("d1", "yes", None) == 1  # already answered: no longer pending


def test_answer_needs_a_valid_option(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    _ask(cli_project)
    assert inbox_answer("d1", None, None) == 1 and "Pick one option" in capsys.readouterr().err
    assert inbox_answer("d1", "maybe", None) == 1 and "is not an option" in capsys.readouterr().err
    assert cli_project.store.conn.execute("SELECT status FROM decisions").fetchone()["status"] == "PENDING"


def test_a_decision_with_a_single_option_needs_no_choice(cli_project: Any) -> None:
    _ask(cli_project, "d2", options=["proceed"])
    assert inbox_answer("d2", None, None) == 0


def test_the_inbox_group_is_registered(cli_project: Any) -> None:
    app = typer.Typer()
    register(app)
    _ask(cli_project)
    runner = CliRunner()
    assert runner.invoke(app, ["inbox", "list", "--output", "plain"]).exit_code == 0
    assert runner.invoke(app, ["inbox", "answer", "d1", "--choice", "no"]).exit_code == 0
