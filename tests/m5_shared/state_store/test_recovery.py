# FILE: tests/m5_shared/state_store/test_recovery.py
# ROLE: Tests that prove src/asf/m5_shared/state_store/recovery.py meets its DONE WHEN conditions.
# ARCH REF: M5; p09 recovery; p14 SEQ-2; D-06; p16 interruption row; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/state_store/recovery.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/state_store/recovery.py: RecoveryReport, reconcile_on_startup (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/state_store/test_recovery.py` on Windows and Linux once src/asf/m5_shared/state_store/recovery.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/state_store/test_recovery.py` and `uv run mypy tests/m5_shared/state_store/test_recovery.py` are clean.

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from asf.m5_shared.state_store.recovery import RecoveryReport, reconcile_on_startup


def test_recovery_report_meets_contract() -> None:
    """Prove RecoveryReport behaves as declared in src/asf/m5_shared/state_store/recovery.py."""
    rep = RecoveryReport(
        runs_checked=2,
        tasks_reset=["task-1"],
        tasks_escalated=["task-2"],
        decisions_rearmed=3,
    )
    assert rep.runs_checked == 2
    assert rep.tasks_reset == ["task-1"]
    assert rep.tasks_escalated == ["task-2"]
    assert rep.decisions_rearmed == 3


def test_reconcile_on_startup_meets_contract(tmp_path: Path, fake_paths: Any) -> None:
    """Prove reconcile_on_startup behaves as declared in src/asf/m5_shared/state_store/recovery.py."""
    _ = fake_paths

    # Set up in-memory or file-backed sqlite database with standard tables
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute("CREATE TABLE runs (run_id TEXT PRIMARY KEY, status TEXT NOT NULL);")
        conn.execute(
            "CREATE TABLE tasks (task_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, state TEXT NOT NULL, "
            "interruption_count INTEGER NOT NULL DEFAULT 0, assigned_worker TEXT, lease_expires_at TEXT);"
        )
        conn.execute("CREATE TABLE leases (task_id TEXT PRIMARY KEY);")
        conn.execute("CREATE TABLE decisions (decision_id TEXT PRIMARY KEY, status TEXT NOT NULL);")

        conn.execute("INSERT INTO runs (run_id, status) VALUES ('run-1', 'RUNNING');")
        # Task 1: running with 1 interruption -> should reset to READY (interruption_count=2)
        conn.execute("INSERT INTO tasks (task_id, run_id, state, interruption_count) VALUES ('t1', 'run-1', 'RUNNING', 1);")
        conn.execute("INSERT INTO leases (task_id) VALUES ('t1');")
        # Task 2: running with 3 interruptions -> should escalate (new count 4 > 3)
        conn.execute("INSERT INTO tasks (task_id, run_id, state, interruption_count) VALUES ('t2', 'run-1', 'RUNNING', 3);")
        # Task 3: VERIFIED -> must NOT be touched
        conn.execute("INSERT INTO tasks (task_id, run_id, state, interruption_count) VALUES ('t3', 'run-1', 'VERIFIED', 0);")
        # Pending decision
        conn.execute("INSERT INTO decisions (decision_id, status) VALUES ('d1', 'PENDING');")

    fake_store = SimpleNamespace(conn=conn)
    fake_workspace = MagicMock()
    fake_runtime = MagicMock()
    fake_broker = MagicMock()

    report = reconcile_on_startup(fake_store, fake_workspace, fake_runtime, fake_broker)  # type: ignore[arg-type]

    assert report.runs_checked == 1
    assert "t1" in report.tasks_reset
    assert "t2" in report.tasks_escalated
    assert report.decisions_rearmed == 1

    # Check updated task states in DB
    cur = conn.execute("SELECT task_id, state, interruption_count FROM tasks")
    states = {row["task_id"]: (row["state"], row["interruption_count"]) for row in cur.fetchall()}
    assert states["t1"] == ("READY", 2)
    assert states["t2"] == ("ESCALATED", 4)
    assert states["t3"] == ("VERIFIED", 0)

    # Check leases cleared
    assert conn.execute("SELECT COUNT(*) FROM leases").fetchone()[0] == 0

    # Check workspace reset was called for t1
    fake_workspace.apply.assert_called_once()
    fake_runtime.drop_stale.assert_called_once()
