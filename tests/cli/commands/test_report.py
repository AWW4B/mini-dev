# FILE: tests/cli/commands/test_report.py
# ROLE: Tests that prove src/asf/cli/commands/report.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02; p04 Deliver report; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/commands/report.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/report.py: report, register (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (stores the report)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_report.py` on Windows and Linux once src/asf/cli/commands/report.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_report.py` and `uv run mypy tests/cli/commands/test_report.py` are clean.

import json
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from asf.cli.commands.report import register, report
from asf.m5_shared.workspace.blobs import BlobStore


def _finish(project: Any, run_id: str = "run1", relayed: bool = True) -> str:
    ref = BlobStore().put(b"# Run run1\nREQ-1: do it\n")
    event = {
        "event_id": "e1", "run_id": run_id, "seq": 1, "ts": "2026-11-12T10:00:00+00:00", "actor": {"kind": "service", "role": "orchestrator", "name": "Orchestrator"},
        "kind": "run_completed", "correlation_id": run_id, "payload": {"report_ref": ref, "status": "DONE"},
    }
    with project.store.conn:
        if relayed:
            project.store.conn.execute(
                "INSERT INTO events (event_id, run_id, seq, timestamp, kind, visibility, source, payload) VALUES ('e1', ?, 1, 't', 'run_completed', 'user', 'o', ?)",
                (run_id, json.dumps(event)),
            )
        else:
            project.store.conn.execute("INSERT INTO outbox (event_id, run_id, payload, published, created_at) VALUES ('e1', ?, ?, 0, 't')", (run_id, json.dumps(event)))
    return ref


def test_the_report_is_printed_with_the_cost(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    cli_project.add_run(status="DONE", cost=1.25, estimated=True)
    _finish(cli_project)
    assert report("run1") == 0
    out = capsys.readouterr().out
    assert "REQ-1: do it" in out and "1.2500 (estimated)" in out


def test_the_report_is_found_before_the_event_relay_has_run(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    cli_project.add_run(status="DONE")
    _finish(cli_project, relayed=False)
    assert report("run1") == 0 and "REQ-1" in capsys.readouterr().out


def test_the_report_can_be_written_to_a_file(cli_project: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli_project.add_run(status="DONE")
    _finish(cli_project)
    dest = tmp_path / "out.md"
    assert report("run1", dest) == 0
    assert "REQ-1: do it" in dest.read_text(encoding="utf-8") and "written to" in capsys.readouterr().out


def test_a_run_without_a_report_says_so(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    cli_project.add_run(status="RUNNING")
    assert report("run1") == 1
    assert "no report yet" in capsys.readouterr().err


def test_the_latest_run_is_used_when_none_is_named(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    cli_project.add_run("old", status="DONE", activity="2026-01-01")
    cli_project.add_run("new", status="DONE", activity="2026-06-01")
    _finish(cli_project, "new")
    assert report("") == 0 and "REQ-1" in capsys.readouterr().out


def test_the_report_command_is_registered(cli_project: Any) -> None:
    app = typer.Typer()
    register(app)
    cli_project.add_run(status="DONE")
    _finish(cli_project)
    assert CliRunner().invoke(app, ["run1"]).exit_code == 0
