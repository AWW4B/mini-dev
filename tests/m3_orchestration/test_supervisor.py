# FILE: tests/m3_orchestration/test_supervisor.py
# ROLE: Tests that prove src/asf/m3_orchestration/supervisor.py meets its DONE WHEN conditions.
# ARCH REF: M3; p04 Escalation & Recovery; IF-10; A-3; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/supervisor.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/supervisor.py: write_supervisor_notes, _cited (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/test_supervisor.py` on Windows and Linux once src/asf/m3_orchestration/supervisor.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/test_supervisor.py` and `uv run mypy tests/m3_orchestration/test_supervisor.py` are clean.

import json
import sqlite3
from pathlib import Path

from asf.m3_orchestration.supervisor import write_supervisor_notes


def _project(tmp_path: Path) -> Path:
    (tmp_path / ".factory" / "logs").mkdir(parents=True)
    conn = sqlite3.connect(tmp_path / ".factory" / "state.db")
    conn.execute("CREATE TABLE tasks (task_id TEXT, state TEXT, title TEXT, created_at TEXT)")
    conn.execute("INSERT INTO tasks VALUES ('t1', 'ESCALATED', 'core', '1')")
    conn.commit()
    conn.close()
    event = {"event": "turn", "task_id": "t1", "data": {"task": "t1", "action": "blocked", "message": "gave up"}}
    (tmp_path / ".factory" / "logs" / "trace.jsonl").write_text(json.dumps(event), encoding="utf-8")
    return tmp_path


def test_recurring_problems_are_counted_across_runs_and_the_notes_say_nothing_was_changed(tmp_path: Path) -> None:
    project = _project(tmp_path)
    write_supervisor_notes(project, analyst=lambda facts: "[]")
    notes = write_supervisor_notes(project, analyst=lambda facts: "[]").read_text(encoding="utf-8")
    assert "Seen 2 time(s)" in notes and "Nothing was changed" in notes


def test_the_agents_proposals_are_kept_only_when_their_evidence_is_in_the_facts(tmp_path: Path) -> None:
    project = _project(tmp_path)
    answer = json.dumps(
        [
            {"change": "show the coder the failing output", "why": "it gave up", "evidence": ["t1"]},
            {"change": "invented", "why": "x", "evidence": ["t-unknown"]},
        ]
    )
    notes = write_supervisor_notes(project, analyst=lambda facts: answer).read_text(encoding="utf-8")
    assert "show the coder the failing output" in notes and "invented" not in notes
    assert "1 proposal(s) were dropped" in notes


def test_an_unreachable_agent_leaves_the_facts_and_says_so(tmp_path: Path) -> None:
    def broken(facts: str) -> str:
        raise RuntimeError("no model")

    notes = write_supervisor_notes(_project(tmp_path), analyst=broken).read_text(encoding="utf-8")
    assert "could not be reached" in notes and "Seen 1 time(s)" in notes


def test_evidence_may_name_a_task_by_its_short_name() -> None:
    from asf.m3_orchestration.supervisor import _cited

    assert _cited("core", {"run_01X-core"}) and not _cited("payments", {"run_01X-core"})
