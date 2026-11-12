# FILE: tests/cli/commands/test_events.py
# ROLE: Tests that prove src/asf/cli/commands/events.py meets its DONE WHEN conditions.
# ARCH REF: M1; p10; D-25; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/commands/events.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/events.py: events_export, register (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
#   - imports from src/asf/contracts/events.py: EventEnvelope (event fixtures)
#   - imports from src/asf/m5_shared/events/event_log.py: EventLog (stores the events)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_events.py` on Windows and Linux once src/asf/cli/commands/events.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_events.py` and `uv run mypy tests/cli/commands/test_events.py` are clean.

import json
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from asf.cli.commands.events import events_export, register
from asf.contracts.events import EventEnvelope
from asf.m5_shared.events.event_log import EventLog


def _events(project: Any, count: int = 3) -> None:
    project.add_run()
    log = EventLog(project.store.conn)
    log.append(
        [
            EventEnvelope.model_validate(
                {
                    "event_id": f"e{i}", "run_id": "run1", "seq": 0, "ts": "2026-11-12T10:00:00+00:00",
                    "actor": {"kind": "agent", "role": "worker", "name": "W"}, "kind": "model_call", "correlation_id": "c",
                    "payload": {"model": "qwen", "tokens_in": 10 * i, "tokens_out": 5, "note": "x"},
                }
            )
            for i in range(1, count + 1)
        ]
    )


def test_jsonl_export_has_one_event_per_line_with_otel_genai_attributes(cli_project: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _events(cli_project)
    dest = tmp_path / "out" / "events.jsonl"
    assert events_export("run1", dest, "jsonl") == 0
    lines = [json.loads(line) for line in dest.read_text(encoding="utf-8").splitlines()]
    assert [e["seq"] for e in lines] == [1, 2, 3]
    assert lines[1]["attributes"] == {"gen_ai.request.model": "qwen", "gen_ai.usage.input_tokens": 20, "gen_ai.usage.output_tokens": 5}
    assert "Wrote 3 event(s)" in capsys.readouterr().out


def test_a_large_run_is_exported_completely(cli_project: Any, tmp_path: Path) -> None:
    _events(cli_project, 1200)
    dest = tmp_path / "big.jsonl"
    events_export("run1", dest, "jsonl")
    assert len(dest.read_text(encoding="utf-8").splitlines()) == 1200


def test_csv_export_writes_the_metric_tables(cli_project: Any, tmp_path: Path) -> None:
    _events(cli_project)
    cli_project.add_call()
    dest = tmp_path / "csv"
    assert events_export("run1", dest, "csv") == 0
    assert {p.name for p in dest.iterdir()} == {"calls.csv", "tools.csv", "limits.csv"}
    assert len((dest / "calls.csv").read_text(encoding="utf-8").splitlines()) == 2


def test_an_unknown_format_is_a_user_error(cli_project: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _events(cli_project)
    assert events_export("run1", tmp_path / "x", "xml") == 1
    assert "Unknown format" in capsys.readouterr().err


def test_the_events_group_is_registered(cli_project: Any, tmp_path: Path) -> None:
    app = typer.Typer()
    register(app)
    _events(cli_project)
    assert CliRunner().invoke(app, ["events", "export", str(tmp_path / "e.jsonl"), "run1"]).exit_code == 0
