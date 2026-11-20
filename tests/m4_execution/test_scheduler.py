# FILE: tests/m4_execution/test_scheduler.py
# ROLE: Tests that prove src/asf/m4_execution/scheduler.py meets its DONE WHEN conditions.
# ARCH REF: M4; p07 Task Scheduler; IF-09; IF-10; IF-13; IF-06; IF-20; IF-21 Requeue; D-06; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m4_execution/scheduler.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m4_execution/scheduler.py: MAX_INFRA_RETRIES, TaskScheduler (unit under test)
#   - imports from src/asf/contracts/outcomes.py: Requeue, TaskOutcome (what the attempt runner returns)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m4_execution/test_scheduler.py` on Windows and Linux once src/asf/m4_execution/scheduler.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m4_execution/test_scheduler.py` and `uv run mypy tests/m4_execution/test_scheduler.py` are clean.

import sqlite3
import threading
from types import SimpleNamespace
from typing import Any

import pytest

from asf.contracts.outcomes import Requeue, TaskOutcome
from asf.m4_execution.scheduler import MAX_INFRA_RETRIES, TaskScheduler


class ContextOverflow(Exception):  # matched by class name, as the real one lives in contracts
    pass


class WorkerBlocked(Exception):
    pass


class _Runtime:
    def __init__(self, slots: int = 1) -> None:
        self.slots = slots
        self.leases: dict[str, Any] = {}
        self.counter = 0
        self.released: list[str] = []

    def max_slots(self) -> int:
        return self.slots

    def acquire(self, request: Any) -> Any:
        if len(self.leases) >= self.slots:
            return None
        self.counter += 1
        lease = SimpleNamespace(lease_id=f"l{self.counter}", model_id=request.model_id, ctx_tokens=request.ctx_tokens, expires_at_monotonic=1e12)
        self.leases[lease.lease_id] = lease
        return lease

    def release(self, lease_id: str) -> None:
        self.leases.pop(lease_id, None)
        self.released.append(lease_id)


def _spec(task_id: str, role: str = "T2", max_attempts: int = 3) -> Any:
    return SimpleNamespace(task_id=task_id, model_role=role, max_attempts=max_attempts)


def _requeue(task_id: str, evidence: str = "sha256:e1") -> Requeue:
    return Requeue.model_validate({"task_id": task_id, "failure_class": "LOCAL_BUG", "evidence_ref": evidence})


def _scheduler(runner: Any, runtime: _Runtime | None = None, **kwargs: Any) -> tuple[TaskScheduler, _Runtime, list[TaskOutcome], list[tuple[str, dict[str, Any]]]]:
    rt = runtime or _Runtime()
    outcomes: list[TaskOutcome] = []
    events: list[tuple[str, dict[str, Any]]] = []
    sched = TaskScheduler(
        runtime=rt, attempt_runner=runner, outcome_sink=outcomes.append, event_sink=lambda k, p: events.append((k, p)), **kwargs  # type: ignore[arg-type]
    )
    return sched, rt, outcomes, events


def test_a_ready_task_runs_to_verified_and_frees_its_slot() -> None:
    sched, rt, outcomes, events = _scheduler(lambda spec, lease, n: None)
    sched.enqueue(_spec("t1"))
    assert sched.state_of("t1") == "READY"
    assert sched.dispatch_ready() == 1
    assert sched.wait_idle()
    assert sched.state_of("t1") == "VERIFIED" and sched.attempts_of("t1") == 1
    assert rt.leases == {} and rt.released == ["l1"]
    assert outcomes == []
    assert [e[1]["to"] for e in events if e[0] == "STATE_CHANGED"] == ["READY", "RUNNING", "VERIFIED"]
    assert any(k == "HANDOFF_SENT" and p["to_role"] == "worker" for k, p in events)
    sched.close()


def test_enqueue_is_idempotent() -> None:
    sched, _, _, events = _scheduler(lambda s, lease, n: None)
    sched.enqueue(_spec("t1"))
    sched.enqueue(_spec("t1"))
    assert len([e for e in events if e[0] == "STATE_CHANGED"]) == 1
    sched.close()


def test_dependencies_hold_a_task_blocked_until_they_are_verified() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE tasks (task_id TEXT PRIMARY KEY, state TEXT)")
    store = SimpleNamespace(
        conn=conn, get_task=lambda task_id: SimpleNamespace(deps=["dep"] if task_id == "child" else [])
    )
    sched, _, _, _ = _scheduler(lambda s, lease, n: None, store=store)
    sched.enqueue(_spec("child"))
    assert sched.state_of("child") == "BLOCKED"
    assert sched.dispatch_ready() == 0
    sched.mark_verified("dep")
    assert sched.state_of("child") == "READY"
    assert sched.dispatch_ready() == 1
    sched.wait_idle()
    sched.close()


def test_a_dependency_already_verified_in_the_store_does_not_block() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE tasks (task_id TEXT PRIMARY KEY, state TEXT)")
    conn.execute("INSERT INTO tasks VALUES ('dep', 'INTEGRATED')")
    store = SimpleNamespace(conn=conn, get_task=lambda task_id: SimpleNamespace(deps=["dep"]))
    sched, _, _, _ = _scheduler(lambda s, lease, n: None, store=store)
    sched.enqueue(_spec("child"))
    assert sched.state_of("child") == "READY"
    sched.close()


def test_the_dispatch_cap_follows_the_runtime_slots_and_advisories() -> None:
    gate = threading.Event()

    def runner(spec: Any, lease: Any, n: int) -> None:
        gate.wait(5)
        return None

    sched, rt, _, _ = _scheduler(runner, _Runtime(slots=2))
    for name in ("a", "b", "c"):
        sched.enqueue(_spec(name))
    sched.on_advisory(SimpleNamespace(max_slots=1))  # type: ignore[arg-type]
    assert sched.dispatch_cap() == 1
    assert sched.dispatch_ready() == 1
    sched.on_advisory(SimpleNamespace(max_slots=None))  # type: ignore[arg-type]
    assert sched.dispatch_cap() == 2
    assert sched.dispatch_ready() == 1  # one more slot, one more task; the third waits for SLOT_FREE
    assert sched.dispatch_ready() == 0
    gate.set()
    sched.wait_idle()
    assert sched.dispatch_ready() == 1
    sched.wait_idle()
    assert rt.leases == {}
    sched.close()


def test_ranking_prefers_the_task_that_unblocks_most_then_the_loaded_model_then_age() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE tasks (task_id TEXT PRIMARY KEY, state TEXT)")
    deps = {"x1": ["hub"], "x2": ["hub"], "x3": ["lone"]}
    store = SimpleNamespace(conn=conn, get_task=lambda tid: SimpleNamespace(deps=deps.get(tid, [])))
    started: list[str] = []
    sched, _, _, _ = _scheduler(lambda spec, lease, n: started.append(str(spec.task_id)), store=store)
    for name in ("lone", "hub", "x1", "x2", "x3"):
        sched.enqueue(_spec(name))
    sched.dispatch_ready()
    sched.wait_idle()
    assert started == ["hub"]  # hub unblocks two tasks, lone only one
    sched.close()


def test_a_fixable_failure_is_requeued_until_attempts_run_out_then_escalated() -> None:
    sched, _, outcomes, _ = _scheduler(lambda spec, lease, n: _requeue("t1", f"sha256:e{n}"))
    sched.enqueue(_spec("t1", max_attempts=2))
    for _ in range(2):
        assert sched.dispatch_ready() == 1
        sched.wait_idle()
    assert sched.attempts_of("t1") == 2
    assert sched.state_of("t1") == "ESCALATED"
    assert [o.failure_class.value for o in outcomes] == ["ESCALATED"]
    assert outcomes[0].attempts == 2 and outcomes[0].evidence_ref == "sha256:e2"
    assert sched.dispatch_ready() == 0
    sched.close()


def test_only_the_newest_failure_evidence_is_kept() -> None:
    sched, _, _, _ = _scheduler(lambda s, lease, n: None)
    sched.enqueue(_spec("t1"))
    sched.requeue(_requeue("t1", "sha256:old"))
    sched.requeue(_requeue("t1", "sha256:new"))
    assert sched.latest_evidence("t1") == "sha256:new"
    sched.close()


def test_a_non_local_outcome_from_the_gate_is_delivered_to_the_orchestrator() -> None:
    outcome = TaskOutcome.model_validate({"task_id": "t1", "failure_class": "CONTRACT_MISMATCH", "evidence_ref": "sha256:x", "attempts": 1})
    sched, _, outcomes, _ = _scheduler(lambda s, lease, n: outcome)
    sched.enqueue(_spec("t1"))
    sched.dispatch_ready()
    sched.wait_idle()
    assert outcomes == [outcome]
    assert sched.state_of("t1") == "ESCALATED"
    sched.close()


def test_context_overflow_and_blocked_workers_become_outcomes() -> None:
    def runner(spec: Any, lease: Any, n: int) -> None:
        raise {"o": ContextOverflow("must-have context needs 9000 tokens"), "g": WorkerBlocked("CONTRACT_GAP: no refund"), "s": WorkerBlocked("SPEC_TOO_LARGE: out of turns")}[str(spec.task_id)]

    sched, _, outcomes, _ = _scheduler(runner, _Runtime(slots=2))
    for name in ("o", "g"):
        sched.enqueue(_spec(name, max_attempts=1))  # a block on the last attempt is a real block
    sched.dispatch_ready()
    sched.wait_idle()
    sched.enqueue(_spec("s"))
    sched.dispatch_ready()
    sched.wait_idle()
    by_task = {str(o.task_id): o.failure_class.value for o in outcomes}
    assert by_task == {"o": "CONTEXT_OVERFLOW", "g": "CONTRACT_GAP", "s": "SPEC_TOO_LARGE"}
    sched.close()


def test_infrastructure_failures_do_not_cost_an_attempt_and_are_capped() -> None:
    def runner(spec: Any, lease: Any, n: int) -> None:
        raise OSError("llama-server did not start")

    sched, _, outcomes, _ = _scheduler(runner)
    sched.enqueue(_spec("t1"))
    for _ in range(MAX_INFRA_RETRIES):
        assert sched.dispatch_ready() == 1
        sched.wait_idle()
        assert sched.state_of("t1") == "READY" and sched.attempts_of("t1") == 0
    assert sched.dispatch_ready() == 1
    sched.wait_idle()
    assert sched.state_of("t1") == "ESCALATED"
    assert [o.failure_class.value for o in outcomes] == ["ENV_INFRA"]
    sched.close()


def test_pause_suspends_waiting_work_and_resume_restores_it() -> None:
    sched, _, _, _ = _scheduler(lambda s, lease, n: None)
    sched.enqueue(_spec("t1"))
    sched.on_cancel(SimpleNamespace(command=SimpleNamespace(value="pause"), task_id=None))  # type: ignore[arg-type]
    assert sched.state_of("t1") == "SUSPENDED"
    assert sched.dispatch_ready() == 0
    sched.on_cancel(SimpleNamespace(command=SimpleNamespace(value="resume"), task_id=None))  # type: ignore[arg-type]
    assert sched.state_of("t1") == "READY"
    assert sched.dispatch_ready() == 1
    sched.wait_idle()
    sched.close()


def test_cancel_task_and_abort_cancel_work_and_never_touch_finished_tasks() -> None:
    sched, _, _, _ = _scheduler(lambda s, lease, n: None, _Runtime(slots=2))
    for name in ("a", "b", "done"):
        sched.enqueue(_spec(name))
    sched.mark_verified("done")
    sched.on_cancel(SimpleNamespace(command=SimpleNamespace(value="cancel_task"), task_id="a"))  # type: ignore[arg-type]
    assert sched.state_of("a") == "CANCELLED" and sched.state_of("b") == "READY"
    sched.on_cancel(SimpleNamespace(command=SimpleNamespace(value="abort"), task_id=None))  # type: ignore[arg-type]
    assert sched.state_of("b") == "CANCELLED" and sched.state_of("done") == "VERIFIED"
    assert sched.dispatch_ready() == 0
    sched.close()


def test_a_running_task_that_is_cancelled_gives_its_slot_back() -> None:
    gate = threading.Event()
    sched, rt, _, _ = _scheduler(lambda s, lease, n: gate.wait(5) and None)
    sched.enqueue(_spec("t1"))
    sched.dispatch_ready()
    sched.on_cancel(SimpleNamespace(command=SimpleNamespace(value="cancel_task"), task_id="t1"))  # type: ignore[arg-type]
    assert rt.leases == {}
    gate.set()
    sched.wait_idle()
    sched.close()


def test_dispatching_without_a_runtime_or_runner_is_an_error() -> None:
    with pytest.raises(RuntimeError):
        TaskScheduler().dispatch_ready()


def test_a_queued_spec_survives_into_a_new_process_as_json() -> None:
    """`factory run resume` is a new process: the leaves a run stopped on must be handed over, or the run waits for them forever."""
    import json

    spec = {
        "task_id": "t1", "goal": "g", "acceptance_test_refs": ["tests/test_a.py"], "capsules": [], "allowed_files": ["src/a.py"],
        "read_only_files": [], "context_budget_tokens": 4096, "model_role": "T2", "base_commit": "abc", "parent_branch": "main",
    }
    first, *_ = _scheduler(lambda *a: None)
    first.enqueue_json(json.dumps(spec))
    saved = first.spec_json("t1")
    assert saved is not None and first.spec_json("nope") is None
    second, *_ = _scheduler(lambda *a: None)
    second.enqueue_json(saved)
    assert second.state_of("t1") in ("READY", "BLOCKED")


def test_an_escalated_task_accepted_by_a_person_is_dispatched_again_with_fresh_attempts() -> None:
    """enqueue ignores a task it holds: the accepted larger leaf of a task the worker had escalated was never run (the run idled forever)."""
    sched, _, _, _ = _scheduler(lambda spec, lease, n: _requeue("t1"))
    sched.enqueue(_spec("t1", max_attempts=1))
    sched.dispatch_ready()
    sched.wait_idle()
    assert sched.state_of("t1") == "ESCALATED"
    sched.reopen(_spec("t1", max_attempts=1))
    assert sched.state_of("t1") == "READY" and sched.attempts_of("t1") == 0
    assert sched.dispatch_ready() == 1
    sched.close()


def test_a_block_before_the_last_attempt_is_retried_so_the_bigger_models_get_their_turn() -> None:
    """One 'blocked' from the 7B coder used to escalate the task at once; the help ladder (20B, then 120B) was never reached."""
    calls: list[int] = []

    def runner(spec: Any, lease: Any, n: int) -> None:
        calls.append(n)
        raise WorkerBlocked("the coder gave up")

    sched, _, outcomes, _ = _scheduler(runner)
    sched.enqueue(_spec("t1", max_attempts=3))
    for _ in range(3):
        sched.dispatch_ready()
        sched.wait_idle()
    assert calls == [1, 2, 3] and [o.failure_class.value for o in outcomes] == ["CONTRACT_GAP"]
    sched.close()
