# FILE: tests/m4_execution/integration/test_integrator.py
# ROLE: Tests that prove src/asf/m4_execution/integration/integrator.py meets its DONE WHEN conditions.
# ARCH REF: M4; p08 Integration & Repair; IF-09 repair tasks; IF-10c RootIntegrated; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m4_execution/integration/integrator.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m4_execution/integration/integrator.py: build_integration_graph, integrate_parent (unit under test)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (the real schema the graph reads and commits to)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m4_execution/integration/test_integrator.py` on Windows and Linux once src/asf/m4_execution/integration/integrator.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m4_execution/integration/test_integrator.py` and `uv run mypy tests/m4_execution/integration/test_integrator.py` are clean.

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from langgraph.checkpoint.memory import MemorySaver

from asf.m4_execution.integration.integrator import build_integration_graph, integrate_parent
from asf.m5_shared.state_store.store import StateStore


class _Blobs:
    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    def put(self, data: bytes) -> str:
        ref = "sha256:" + hashlib.sha256(data).hexdigest()
        self.data[ref] = data
        return ref


def _workspace(tmp_path: Path) -> Any:
    return SimpleNamespace(repo_dir=tmp_path, blobs=_Blobs(), _run_git=lambda args, cwd=None: (0, "abc123", ""))


def _runner(code: int = 0, out: str = "all passed", timed_out: bool = False) -> Any:
    calls: list[list[str]] = []

    def run(argv: list[str], cwd: Path, timeout_s: int) -> Any:
        calls.append(argv)
        return SimpleNamespace(exit_code=code, stdout=out.encode(), stderr=b"", timed_out=timed_out)

    run.calls = calls  # type: ignore[attr-defined]
    return run


class _Scheduler:
    def __init__(self) -> None:
        self.enqueued: list[Any] = []
        self.verified: list[str] = []

    def enqueue(self, spec: Any) -> None:
        self.enqueued.append(spec)

    def mark_verified(self, task_id: str) -> None:
        self.verified.append(task_id)


class _Registry:
    def __init__(self) -> None:
        self.promoted: list[tuple[str, str]] = []

    def promote(self, contract_id: str, status: Any) -> None:
        self.promoted.append((contract_id, status.value))


def _add(store: StateStore, task_id: str, state: str, parent: str | None = None, **extra: Any) -> None:
    payload = {
        "id": task_id, "run_id": "run-1", "parent_id": parent, "kind": "composite" if parent is None or task_id.startswith("p") else "leaf",
        "goal": f"goal of {task_id}", "idempotency_key": f"k-{task_id}", "state": state, "counters": {"repair_rounds": 0}, **extra,
    }
    with store.conn:
        store.conn.execute(
            "INSERT INTO tasks (task_id, run_id, parent_id, state, kind, version, title, payload) VALUES (?, 'run-1', ?, ?, ?, 1, 'g', ?)",
            (task_id, parent, state, payload["kind"], json.dumps(payload)),
        )


def _state_of(store: StateStore, task_id: str) -> str:
    return str(store.conn.execute("SELECT state FROM tasks WHERE task_id = ?", (task_id,)).fetchone()["state"])


def _events(store: StateStore) -> list[dict[str, Any]]:
    return [json.loads(r["payload"]) for r in store.conn.execute("SELECT payload FROM outbox ORDER BY id")]


def _setup(tmp_path: Path, child_states: tuple[str, ...] = ("VERIFIED", "INTEGRATED"), root: bool = True, **parent_extra: Any) -> StateStore:
    store = StateStore.open(tmp_path / "state.db")
    _add(store, "p1", "CHILDREN_DONE", None if root else "top", **parent_extra)
    if not root:
        _add(store, "top", "DECOMPOSED", None)
    for i, state in enumerate(child_states):
        _add(store, f"c{i}", state, "p1", allowed_files=[f"src/mod{i}.py"], acceptance_refs=[f"tests/test_mod{i}.py"])
    return store


def _integrate(store: StateStore, tmp_path: Path, runner: Any, **kwargs: Any) -> Any:
    return integrate_parent("p1", state_store=store, workspace=_workspace(tmp_path), test_runner=runner, **kwargs)


def test_nothing_happens_until_every_child_is_verified_or_integrated(tmp_path: Path) -> None:
    store = _setup(tmp_path, child_states=("VERIFIED", "RUNNING"))
    runner = _runner()
    assert _integrate(store, tmp_path, runner) is None
    assert runner.calls == []
    assert _state_of(store, "p1") == "CHILDREN_DONE"


def test_a_parent_without_children_is_not_integrated(tmp_path: Path) -> None:
    store = _setup(tmp_path, child_states=())
    runner = _runner()
    assert _integrate(store, tmp_path, runner) is None and runner.calls == []


def test_a_green_root_is_integrated_and_publishes_root_integrated(tmp_path: Path) -> None:
    store = _setup(tmp_path, contract_refs=["billing@1.0.0"])
    registry = _Registry()
    ws = _workspace(tmp_path)
    runner = _runner(out="12 passed")

    result = integrate_parent("p1", state_store=store, workspace=ws, test_runner=runner, registry=registry)

    assert result is not None
    assert type(result).__name__ == "RootIntegrated"
    assert result.root_task == "p1" and result.run_id == "run-1"
    assert b"12 passed" in ws.blobs.data[result.report_ref]
    assert _state_of(store, "p1") == "INTEGRATED"
    assert registry.promoted == [("billing", "STABLE")]
    kinds = [(e["kind"], e["payload"].get("to") or e["payload"].get("passed")) for e in _events(store)]
    assert kinds == [("state_changed", "INTEGRATING"), ("gate_result", True), ("state_changed", "INTEGRATED")]


def test_a_green_non_root_counts_as_a_verified_child_of_its_parent(tmp_path: Path) -> None:
    store = _setup(tmp_path, root=False)
    scheduler = _Scheduler()
    assert _integrate(store, tmp_path, _runner(), scheduler=scheduler) is None
    assert _state_of(store, "p1") == "INTEGRATED"
    assert scheduler.verified == ["p1"]


def test_a_red_run_creates_a_scoped_repair_leaf_and_counts_the_round(tmp_path: Path) -> None:
    store = _setup(tmp_path, allowed_files=["src/mod0.py", "src/mod1.py"])
    scheduler = _Scheduler()
    log = "FAILED tests/test_mod1.py::test_total - assert 1 == 2\nFAILED tests/test_mod1.py::test_tax\n2 failed"

    assert _integrate(store, tmp_path, _runner(1, log), scheduler=scheduler) is None

    assert _state_of(store, "p1") == "REPAIRING"
    payload = json.loads(store.conn.execute("SELECT payload FROM tasks WHERE task_id = 'p1'").fetchone()["payload"])
    assert payload["counters"]["repair_rounds"] == 1
    (spec,) = scheduler.enqueued
    assert spec.task_id == "p1-repair-1"
    assert spec.acceptance_test_refs == ["tests/test_mod1.py::test_total", "tests/test_mod1.py::test_tax"]
    assert spec.allowed_files == ["src/mod0.py", "src/mod1.py"]
    assert spec.base_commit == "abc123"


def test_exhausted_repair_rounds_escalate_with_the_report_as_evidence(tmp_path: Path) -> None:
    store = _setup(tmp_path, counters={"repair_rounds": 2})
    sunk: list[Any] = []
    assert _integrate(store, tmp_path, _runner(1, "FAILED tests/test_x.py::test_a"), scheduler=_Scheduler(), outcome_sink=sunk.append) is None
    assert _state_of(store, "p1") == "ESCALATED"
    assert len(sunk) == 1 and sunk[0].failure_class.value == "ESCALATED" and sunk[0].task_id == "p1"


def test_a_timed_out_integration_run_is_red(tmp_path: Path) -> None:
    store = _setup(tmp_path)
    scheduler = _Scheduler()
    _integrate(store, tmp_path, _runner(0, "", timed_out=True), scheduler=scheduler)
    assert _state_of(store, "p1") == "REPAIRING" and len(scheduler.enqueued) == 1


def test_the_test_command_can_be_overridden(tmp_path: Path) -> None:
    store = _setup(tmp_path)
    runner = _runner()
    _integrate(store, tmp_path, runner, test_command=["pytest", "tests/integration"])
    assert runner.calls == [["pytest", "tests/integration"]]


def test_missing_collaborators_are_reported_clearly(tmp_path: Path) -> None:
    graph = build_integration_graph(None)
    with pytest.raises(RuntimeError, match="state_store"):
        graph.invoke({"parent_id": "p1"}, {"configurable": {}})


def test_the_graph_also_compiles_with_a_checkpointer(tmp_path: Path) -> None:
    store = _setup(tmp_path)
    graph = build_integration_graph(MemorySaver())
    config: Any = {"configurable": {"thread_id": "t", "state_store": store, "workspace": _workspace(tmp_path), "test_runner": _runner()}}
    out = graph.invoke({"parent_id": "p1"}, config)
    assert type(out["result"]).__name__ == "RootIntegrated"
