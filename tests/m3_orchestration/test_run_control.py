# FILE: tests/m3_orchestration/test_run_control.py
# ROLE: Tests that prove src/asf/m3_orchestration/run_control.py meets its DONE WHEN conditions.
# ARCH REF: M3; p04 Run Control; IF-05 RunControl; IF-06 CancelSignal; D-15; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/run_control.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/run_control.py: RunSupervisor (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
#   - imports from src/asf/contracts/control.py: RunControl (command fixtures)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (the command table and run rows)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/test_run_control.py` on Windows and Linux once src/asf/m3_orchestration/run_control.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/test_run_control.py` and `uv run mypy tests/m3_orchestration/test_run_control.py` are clean.

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from asf.contracts.control import RunControl
from asf.m3_orchestration.run_control import RunSupervisor
from asf.m5_shared.state_store.store import StateStore


def _cmd(command_id: str, command: str, run_id: str = "run1", task_id: str | None = None) -> RunControl:
    return RunControl.model_validate({"command_id": command_id, "run_id": run_id, "command": command, "task_id": task_id})


class _Scheduler:
    def __init__(self) -> None:
        self.signals: list[Any] = []

    def on_cancel(self, signal: Any) -> None:
        self.signals.append(signal)


class _Runtime:
    def __init__(self) -> None:
        self.dropped = 0

    def drop_stale(self) -> int:
        self.dropped += 1
        return 0


class _Platform:
    def __init__(self) -> None:
        self.handler: Any = None

    def install_interrupt_handler(self, on_interrupt: Any) -> None:
        self.handler = on_interrupt


def _store(tmp_path: Path) -> StateStore:
    store = StateStore.open(tmp_path / "state.db")
    with store.conn:
        store.conn.execute(
            "INSERT INTO runs (run_id, project_id, status, version, created_at, last_activity, cost, cost_estimated, payload) "
            "VALUES ('run1', 'p', 'RUNNING', 1, 't', 't', 2.5, 0, '{}')"
        )
    return store


def _status(store: StateStore) -> tuple[str, float]:
    row = store.conn.execute("SELECT status, cost FROM runs WHERE run_id = 'run1'").fetchone()
    return str(row["status"]), float(row["cost"])


def _events(store: StateStore) -> list[dict[str, Any]]:
    return [json.loads(r["payload"]) for r in store.conn.execute("SELECT payload FROM outbox ORDER BY id")]


def test_pause_records_the_status_emits_an_event_and_broadcasts_to_the_scheduler(tmp_path: Path) -> None:
    store, scheduler = _store(tmp_path), _Scheduler()
    sup = RunSupervisor("run1", store=store, scheduler=scheduler)  # type: ignore[arg-type]
    signal = sup.apply(_cmd("c1", "pause"))
    assert signal is not None and signal.scope == "run" and signal.command.value == "pause" and signal.task_id is None
    assert sup.status == "PAUSED" and _status(store) == ("PAUSED", 2.5)
    assert scheduler.signals == [signal]
    (event,) = _events(store)
    assert event["kind"] == "state_changed" and event["payload"]["status"] == "PAUSED"


def test_abort_cancels_the_run_emits_cancelled_and_drops_stale_leases(tmp_path: Path) -> None:
    store, runtime = _store(tmp_path), _Runtime()
    sup = RunSupervisor("run1", store=store, runtime=runtime)  # type: ignore[arg-type]
    assert sup.apply(_cmd("c1", "abort")) is not None
    assert _status(store)[0] == "CANCELLED" and runtime.dropped == 1
    assert _events(store)[0]["kind"] == "cancelled"


def test_cancel_task_is_scoped_to_the_task_and_keeps_the_run_status_and_cost(tmp_path: Path) -> None:
    store = _store(tmp_path)
    sup = RunSupervisor("run1", store=store)
    signal = sup.apply(_cmd("c1", "cancel_task", task_id="t9"))
    assert signal is not None and signal.scope == "task" and signal.task_id == "t9"
    assert _status(store) == ("RUNNING", 2.5)
    assert _events(store)[0]["kind"] == "cancelled" and _events(store)[0]["task_id"] == "t9"


def test_cancel_task_without_a_task_is_ignored() -> None:
    assert RunSupervisor("run1").apply(_cmd("c1", "cancel_task")) is None


def test_the_same_command_id_is_applied_once() -> None:
    sup = RunSupervisor("run1")
    assert sup.apply(_cmd("c1", "pause")) is not None
    assert sup.apply(_cmd("c1", "pause")) is None
    assert len(sup.signals) == 1


def test_commands_for_another_run_are_not_authorised() -> None:
    sup = RunSupervisor("run1")
    assert sup.apply(_cmd("c1", "abort", run_id="someone-elses-run")) is None
    assert sup.status == "RUNNING"


def test_resume_needs_a_paused_run_and_reconciles_before_broadcasting(tmp_path: Path) -> None:
    order: list[str] = []
    scheduler = _Scheduler()
    sup = RunSupervisor("run1", store=_store(tmp_path), scheduler=scheduler, reconcile=lambda: order.append("reconcile"))  # type: ignore[arg-type]
    assert sup.apply(_cmd("c0", "resume")) is None  # not paused
    sup.apply(_cmd("c1", "pause"))
    signal = sup.apply(_cmd("c2", "resume"))
    assert signal is not None and sup.status == "RUNNING" and order == ["reconcile"]
    assert scheduler.signals[-1] is signal


def test_nothing_is_applied_to_a_finished_run() -> None:
    sup = RunSupervisor("run1")
    sup.apply(_cmd("c1", "abort"))
    assert sup.apply(_cmd("c2", "pause")) is None and sup.status == "CANCELLED"


def test_poll_once_applies_the_commands_the_cli_wrote(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.put_command(_cmd("c1", "pause"))
    store.put_command(_cmd("c2", "cancel_task", task_id="t1"))
    sup = RunSupervisor("run1", store=store)
    assert sup.poll_once() == 2
    assert sup.poll_once() == 0  # consumed
    assert sup.status == "PAUSED"


def test_the_loop_waits_for_commands_and_returns_when_the_run_is_paused(tmp_path: Path) -> None:
    store, platform = _store(tmp_path), _Platform()
    ticks: list[float] = []

    def sleep(seconds: float) -> None:
        ticks.append(seconds)
        if len(ticks) == 2:
            store.put_command(_cmd("c1", "pause"))

    RunSupervisor("run1", store=store, platform=platform, sleep=sleep, poll_interval_s=0.25).loop()
    assert ticks == [0.25, 0.25] and _status(store)[0] == "PAUSED"


def test_ctrl_c_becomes_a_clean_pause(tmp_path: Path) -> None:
    store, platform = _store(tmp_path), _Platform()

    def sleep(seconds: float) -> None:
        platform.handler()  # the user presses Ctrl+C

    sup = RunSupervisor("run1", store=store, platform=platform, sleep=sleep)
    sup.loop()
    assert sup.status == "PAUSED" and _status(store)[0] == "PAUSED"
    assert str(sup.signals[0].command.value) == "pause"


def test_the_loop_ends_when_the_run_is_finished_elsewhere(tmp_path: Path) -> None:
    store = _store(tmp_path)
    calls = {"n": 0}

    def sleep(seconds: float) -> None:
        calls["n"] += 1
        with store.conn:
            store.conn.execute("UPDATE runs SET status = 'DONE' WHERE run_id = 'run1'")

    sup = RunSupervisor("run1", store=store, platform=_Platform(), sleep=sleep)
    sup.loop()
    assert sup.status == "DONE" and calls["n"] == 1
    _ = SimpleNamespace
