# FILE: tests/m5_shared/state_store/test_store.py
# ROLE: Tests that prove src/asf/m5_shared/state_store/store.py meets its DONE WHEN conditions.
# ARCH REF: M5; p09 Project State Store; IF-16 StateCommit; IF-24 HistoryQuery; IF-05 command table (D-15); D-05; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/state_store/store.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/state_store/test_store.py` on Windows and Linux once src/asf/m5_shared/state_store/store.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/state_store/test_store.py` and `uv run mypy tests/m5_shared/state_store/test_store.py` are clean.

from pathlib import Path
from types import SimpleNamespace

import pytest

from asf.m5_shared.state_store.store import StateStore


def test_state_store_meets_contract(tmp_path: Path) -> None:
    """Prove StateStore behaves as declared in src/asf/m5_shared/state_store/store.py."""
    db_path = tmp_path / "test_store.db"
    store = StateStore.open(db_path)

    # 1. Commit new run
    run_commit = SimpleNamespace(
        entity="runs",
        entity_id="run-1",
        expected_version=None,
        mutation={
            "project_id": "proj-1",
            "status": "RUNNING",
            "cost": 1.25,
            "cost_estimated": False,
        },
        events=[],
    )
    v1 = store.commit(run_commit)  # type: ignore[arg-type]
    assert v1 == 1

    # 2. Conflict on re-creating run
    with pytest.raises(Exception, match=r"(?i)conflict|expected"):
        store.commit(run_commit)  # type: ignore[arg-type]

    # 3. Optimistic concurrency check update run
    run_update = SimpleNamespace(
        entity="runs",
        entity_id="run-1",
        expected_version=1,
        mutation={
            "status": "COMPLETED",
            "cost": 2.50,
        },
        events=[],
    )
    v2 = store.commit(run_update)  # type: ignore[arg-type]
    assert v2 == 2

    # 4. Commit a task node
    task_commit = SimpleNamespace(
        entity="tasks",
        entity_id="task-1",
        expected_version=None,
        mutation={
            "id": "task-1",
            "run_id": "run-1",
            "kind": "composite",
            "goal": "Build payment module",
            "state": "READY",
            "idempotency_key": "idem-1",
        },
        events=[],
    )
    tv1 = store.commit(task_commit)  # type: ignore[arg-type]
    assert tv1 == 1

    # 5. Retrieve task
    task = store.get_task("task-1")
    assert task.id == "task-1"
    assert task.run_id == "run-1"
    assert task.goal == "Build payment module"
    assert task.state.value == "READY"

    # Missing task raises KeyError
    with pytest.raises(KeyError):
        store.get_task("missing-task")

    # 6. tasks_in_state
    tasks = store.tasks_in_state("run-1", task.state)
    assert len(tasks) == 1
    assert tasks[0].id == "task-1"

    # 7. put_command & poll_commands
    cmd = SimpleNamespace(
        command_id="cmd-1",
        run_id="run-1",
        command=SimpleNamespace(value="pause"),
        task_id=None,
    )
    store.put_command(cmd)  # type: ignore[arg-type]
    polled = store.poll_commands("run-1")
    assert len(polled) == 1
    assert polled[0].command_id == "cmd-1"
    assert polled[0].command.value == "pause"

    # Polling again yields empty list (marked consumed)
    assert store.poll_commands("run-1") == []

    # 8. history query
    hist_query = SimpleNamespace(
        project_id="proj-1",
        run_id=None,
        limit=10,
    )
    history_res = store.history(hist_query)  # type: ignore[arg-type]
    assert len(history_res.runs) == 1
    assert history_res.runs[0].run_id == "run-1"
    assert history_res.runs[0].project_id == "proj-1"
    assert history_res.runs[0].status == "COMPLETED"

    # 9. Readonly open
    ro_store = StateStore.open(db_path, readonly=True)
    ro_task = ro_store.get_task("task-1")
    assert ro_task.id == "task-1"
    ro_store.close()

    # 10. Close writer
    store.close()
