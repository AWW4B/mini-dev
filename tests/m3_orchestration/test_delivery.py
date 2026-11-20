# FILE: tests/m3_orchestration/test_delivery.py
# ROLE: Tests that prove src/asf/m3_orchestration/delivery.py meets its DONE WHEN conditions.
# ARCH REF: M3; p04 Escalation & Recovery; IF-10; A-3; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/delivery.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/delivery.py: build_report, write_delivery (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/test_delivery.py` on Windows and Linux once src/asf/m3_orchestration/delivery.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/test_delivery.py` and `uv run mypy tests/m3_orchestration/test_delivery.py` are clean.

import json
import sqlite3
import zipfile
from pathlib import Path

from asf.m3_orchestration.delivery import build_report, write_delivery


def _project(tmp_path: Path) -> Path:
    (tmp_path / ".factory" / "logs").mkdir(parents=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "core.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=1\n", encoding="utf-8")
    conn = sqlite3.connect(tmp_path / ".factory" / "state.db")
    conn.execute("CREATE TABLE tasks (task_id TEXT, state TEXT, title TEXT, created_at TEXT)")
    conn.executemany("INSERT INTO tasks VALUES (?, ?, ?, ?)", [("t-core", "ESCALATED", "core", "1"), ("t-doc", "VERIFIED", "doc", "2")])
    conn.commit()
    conn.close()
    events = [
        {"event": "attempt_start", "task_id": "t-core", "data": {"task": "t-core"}},
        {"event": "turn", "task_id": "t-core", "data": {"task": "t-core", "action": "blocked", "message": "tests fail"}},
        {"event": "helper_model", "task_id": "t-core", "data": {"task": "t-core"}},
    ]
    (tmp_path / ".factory" / "logs" / "trace.jsonl").write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    return tmp_path


def test_the_report_lists_each_problem_with_cause_and_fix_and_not_the_verified_tasks(tmp_path: Path) -> None:
    text = build_report(_project(tmp_path))
    assert "| t-core | ESCALATED | 1 | yes |" in text and "### t-core (ESCALATED)" in text
    assert "Cause:" in text and "Probable fix:" in text and "### t-doc" not in text
    assert "1 of 2 tasks are verified" in text


def test_the_archive_holds_the_project_and_the_report_but_no_secrets_or_run_data(tmp_path: Path) -> None:
    report, archive = write_delivery(_project(tmp_path))
    names = set(zipfile.ZipFile(archive).namelist())
    assert names == {"src/core.py", "REPORT.md"} and report.is_file()


def test_a_run_that_never_created_tasks_is_not_reported_as_all_verified(tmp_path: Path) -> None:
    """The first real autopilot run ended on a rejected plan and the report said 'None: every task is verified'."""
    (tmp_path / ".factory").mkdir()
    conn = sqlite3.connect(tmp_path / ".factory" / "state.db")
    conn.execute("CREATE TABLE tasks (task_id TEXT, state TEXT, title TEXT, created_at TEXT)")
    conn.execute("CREATE TABLE runs (run_id TEXT, status TEXT)")
    conn.execute("INSERT INTO runs VALUES ('r1', 'FAILED')")
    conn.commit()
    conn.close()
    text = build_report(tmp_path)
    assert "every task is verified" not in text and "did not finish (status FAILED)" in text and "No task was ever created" in text
