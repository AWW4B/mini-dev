# FILE: tests/m5_shared/state_store/test_recovery.py
# ROLE: Tests that prove src/asf/m5_shared/state_store/recovery.py meets its DONE WHEN conditions.
# ARCH REF: M5; p09 recovery; p14 SEQ-2; D-06; p16 interruption row; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/state_store/recovery.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/state_store/recovery.py: RecoveryError, RecoveryReport, reconcile_on_startup (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (the real schema the recovery runs against)
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

import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from asf.m5_shared.state_store.recovery import RecoveryError, RecoveryReport, reconcile_on_startup
from asf.m5_shared.state_store.store import StateStore


def _store(tmp_path: Path) -> StateStore:
    store = StateStore.open(tmp_path / "state.db")
    with store.conn:
        store.conn.execute(
            "INSERT INTO runs (run_id, project_id, status, version, created_at, last_activity, cost, cost_estimated, payload) "
            "VALUES ('run-1', 'p', 'RUNNING', 1, 't', 't', 0, 0, '{}')"
        )
    return store


def _add_task(store: StateStore, task_id: str, state: str, interruptions: int = 0, with_lease: bool = False) -> None:
    payload = {
        "id": task_id, "run_id": "run-1", "state": state, "kind": "leaf", "goal": "g",
        "counters": {"interruptions": interruptions, "attempts": 2},
    }
    with store.conn:
        store.conn.execute(
            "INSERT INTO tasks (task_id, run_id, state, kind, version, title, payload) VALUES (?, 'run-1', ?, 'leaf', 1, 'g', ?)",
            (task_id, state, json.dumps(payload)),
        )
        if with_lease:
            store.conn.execute(
                "INSERT INTO leases (lease_id, task_id, worker_id, expires_at) VALUES (?, ?, 'w', 't')", (f"l-{task_id}", task_id)
            )


def _task(store: StateStore, task_id: str) -> tuple[str, int, dict[str, Any]]:
    row = store.conn.execute("SELECT state, version, payload FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    return str(row["state"]), int(row["version"]), json.loads(row["payload"])


def _outbox(store: StateStore) -> list[dict[str, Any]]:
    return [json.loads(r["payload"]) for r in store.conn.execute("SELECT payload FROM outbox ORDER BY id")]


def _run(store: StateStore, workspace: Any = None, runtime: Any = None) -> RecoveryReport:
    return reconcile_on_startup(store, workspace or MagicMock(), runtime or MagicMock(), MagicMock())


def test_recovery_report_meets_contract() -> None:
    rep = RecoveryReport(runs_checked=2, tasks_reset=["task-1"], tasks_escalated=["task-2"], decisions_rearmed=3)
    assert (rep.runs_checked, rep.tasks_reset, rep.tasks_escalated, rep.decisions_rearmed) == (2, ["task-1"], ["task-2"], 3)


def test_interrupted_task_is_reset_through_the_real_schema(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    store = _store(tmp_path)
    _add_task(store, "t1", "RUNNING", interruptions=1, with_lease=True)
    workspace = MagicMock()

    report = _run(store, workspace)

    assert report.tasks_reset == ["t1"] and report.tasks_escalated == []
    state, version, payload = _task(store, "t1")
    assert state == "READY" and version == 2
    assert payload["state"] == "READY" and payload["prior_state"] == "RUNNING"
    assert payload["counters"] == {"interruptions": 2, "attempts": 2}
    assert store.conn.execute("SELECT COUNT(*) FROM leases").fetchone()[0] == 0
    op = workspace.apply.call_args.args[0]
    assert op.kind.value == "reset_to_base" and op.task_id == "t1"


def test_task_with_too_many_interruptions_is_escalated_and_its_worktree_untouched(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    store = _store(tmp_path)
    _add_task(store, "t2", "RUNNING", interruptions=3)
    workspace = MagicMock()

    report = _run(store, workspace)

    assert report.tasks_escalated == ["t2"] and report.tasks_reset == []
    assert _task(store, "t2")[0] == "ESCALATED"
    workspace.apply.assert_not_called()


@pytest.mark.parametrize("state", ["VERIFIED", "INTEGRATED", "READY", "BLOCKED"])
def test_tasks_that_were_not_running_are_never_modified(tmp_path: Path, fake_paths: Any, state: str) -> None:
    _ = fake_paths
    store = _store(tmp_path)
    _add_task(store, "t3", state)
    before = _task(store, "t3")
    assert _run(store).tasks_reset == []
    assert _task(store, "t3") == before


def test_state_change_and_run_recovered_events_are_committed_with_the_transition(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    store = _store(tmp_path)
    _add_task(store, "a", "RUNNING")
    _add_task(store, "b", "RUNNING")
    _run(store)

    events = _outbox(store)
    kinds = [e["kind"] for e in events]
    assert kinds.count("state_changed") == 2
    assert kinds.count("run_recovered") == 1  # once per run, not per task
    assert {e["task_id"] for e in events if e["kind"] == "state_changed"} == {"a", "b"}
    assert len({e["event_id"] for e in events}) == len(events)


def test_a_second_recovery_changes_nothing(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    store = _store(tmp_path)
    _add_task(store, "t1", "RUNNING")
    _run(store)
    snapshot = (_task(store, "t1"), len(_outbox(store)))
    report = _run(store)
    assert report.tasks_reset == [] and report.tasks_escalated == []
    assert (_task(store, "t1"), len(_outbox(store))) == snapshot


def test_worktree_reset_failure_leaves_the_task_running_and_is_reported(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    store = _store(tmp_path)
    _add_task(store, "bad", "RUNNING", with_lease=True)
    _add_task(store, "ok", "RUNNING")

    def fail_for_bad(op: Any) -> None:
        if op.task_id == "bad":
            raise RuntimeError("git failed")

    workspace = MagicMock()
    workspace.apply.side_effect = fail_for_bad

    with pytest.raises(RecoveryError) as info:
        _run(store, workspace)

    assert "bad" in str(info.value)
    assert _task(store, "bad")[0] == "RUNNING"  # retried on the next start
    assert store.conn.execute("SELECT COUNT(*) FROM leases WHERE task_id = 'bad'").fetchone()[0] == 1
    assert _task(store, "ok")[0] == "READY"  # the others were still recovered


def test_runtime_failure_is_logged_not_swallowed_and_does_not_stop_recovery(
    tmp_path: Path, fake_paths: Any, caplog: pytest.LogCaptureFixture
) -> None:
    _ = fake_paths
    store = _store(tmp_path)
    runtime = MagicMock()
    runtime.drop_stale.side_effect = OSError("nvml gone")
    with caplog.at_level(logging.WARNING):
        report = _run(store, runtime=runtime)
    assert report.runs_checked == 1
    assert any("re-probe failed" in r.getMessage() for r in caplog.records)


def test_pending_decisions_are_counted(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    store = _store(tmp_path)
    with store.conn:
        for i, status in enumerate(["PENDING", "PENDING", "RESOLVED"]):
            store.conn.execute(
                "INSERT INTO decisions (decision_id, run_id, topic, status, version, payload) VALUES (?, 'run-1', 'clarify', ?, 1, '{}')",
                (f"d{i}", status),
            )
    assert _run(store).decisions_rearmed == 2
