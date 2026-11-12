# FILE: tests/m3_orchestration/test_run_graph.py
# ROLE: Tests that prove src/asf/m3_orchestration/run_graph.py meets its DONE WHEN conditions.
# ARCH REF: M3; p01 HLD; p04 Main Orchestrator; p13 SEQ-1 happy path; p14 SEQ-2 recovery; IF-02; IF-10b; IF-10c; D-04; D-05; D-06; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/run_graph.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/run_graph.py: build_run_graph, start_run, resume_run (unit under test)
#   - imports from src/asf/contracts/requests.py: StructuredRequest (request fixtures)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (the real decision table)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (the real run and task tables)
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (report blobs)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/test_run_graph.py` on Windows and Linux once src/asf/m3_orchestration/run_graph.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/test_run_graph.py` and `uv run mypy tests/m3_orchestration/test_run_graph.py` are clean.

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from asf.contracts.requests import StructuredRequest
from asf.m3_orchestration.run_graph import build_run_graph, resume_run, start_run
from asf.m5_shared.decisions.broker import DecisionBroker
from asf.m5_shared.state_store.store import StateStore
from asf.m5_shared.workspace.blobs import BlobStore

RUN = "run1"


def _request(task_type: str = "feature", reqs: tuple[str, ...] = ("REQ-1",)) -> StructuredRequest:
    return StructuredRequest.model_validate(
        {
            "request_id": "q1", "project_id": "p1", "task_type": task_type,
            "requirements": [{"req_id": r, "text": f"do {r}", "source_ref": "prompt"} for r in reqs],
        }
    )


def _module(name: str, covers: list[str]) -> dict[str, Any]:
    return {
        "name": name, "goal": f"implement the {name} module with care", "files": [f"src/{name}.py"], "covers": covers,
        "acceptance": [f"{name} works"], "interfaces": [{"name": f"{name}_op", "signature": f"{name}_op() -> None"}],
    }


class _Gateway:
    def __init__(self, *plans: dict[str, Any]) -> None:
        self.plans = list(plans)
        self.prompts: list[str] = []

    def model_for(self, role: Any, purpose: str, output_schema: Any = None, task_id: Any = None) -> Any:
        outer = self

        class _Model:
            def invoke(self, prompt: str) -> Any:
                if purpose == "rubric":
                    return {"ambiguity": 0.1, "coupling": 0.1, "notes": "scripted"}
                if purpose == "plan_critique":
                    return SimpleNamespace(content="NO_ISSUES")
                outer.prompts.append(prompt)
                return outer.plans.pop(0) if len(outer.plans) > 1 else outer.plans[0]

        return _Model()


class _Scheduler:
    def __init__(self) -> None:
        self.specs: list[Any] = []

    def enqueue(self, spec: Any) -> None:
        self.specs.append(spec)


class _Acceptance:
    """Scripted final acceptance: each call pops the next verdict."""

    def __init__(self, *verdicts: tuple[bool, list[str]]) -> None:
        self.verdicts = list(verdicts)
        self.calls: list[StructuredRequest] = []

    def __call__(self, request: StructuredRequest, root: Path, regression: Any = None, blobs: Any = None) -> Any:
        self.calls.append(request)
        passed, untraced = self.verdicts.pop(0) if len(self.verdicts) > 1 else self.verdicts[0]
        data = {"passed": passed, "untraced": untraced, "failing_tests": [], "report_ref": "sha256:acceptance"}
        return SimpleNamespace(model_dump=lambda mode=None: data, **data)


def _set_root(store: StateStore, root_id: str, state: str) -> None:
    payload = {"id": root_id, "run_id": RUN, "kind": "composite", "goal": "g", "idempotency_key": "k", "state": state}
    with store.conn:
        store.conn.execute("UPDATE tasks SET state = ?, payload = ? WHERE task_id = ?", (state, json.dumps(payload), root_id))


def _set_all(store: StateStore, *root_ids: str) -> None:
    for root_id in root_ids:
        _set_root(store, root_id, "INTEGRATED")


def _driver(store: StateStore, root_id: str, final: str = "INTEGRATED") -> Any:
    def tick() -> None:
        _set_root(store, root_id, final)  # stands in for the scheduler, workers, gate and integrator

    return tick


def _overrides(tmp_path: Path, store: StateStore, gateway: _Gateway, acceptance: Any, **extra: Any) -> dict[str, Any]:
    return {
        "run_id": RUN, "state_store": store, "gateway": gateway, "scheduler": _Scheduler(), "acceptance": acceptance,
        "profile": SimpleNamespace(c_eff_tokens=10_000), "blobs": BlobStore(tmp_path / "blobs"), "checkpointer": MemorySaver(),
        "authoring": lambda node: [f"tests/test_{str(node.id).split('-')[-1]}.py"], "planner_strategy": "single_pass",
        "driver": _driver(store, f"{RUN}-root"), "sleep": lambda s: None, **extra,
    }


def _status(store: StateStore) -> str:
    return str(store.conn.execute("SELECT status FROM runs WHERE run_id = ?", (RUN,)).fetchone()["status"])


def _kinds(store: StateStore) -> list[str]:
    return [json.loads(r["payload"])["kind"] for r in store.conn.execute("SELECT payload FROM outbox ORDER BY id")]


def _answer(decision_id: str, choice: str) -> Any:
    now = datetime.now(UTC)
    return SimpleNamespace(
        decision_id=decision_id, choice=choice, text=None, answered_by="user", answered_at=now, applied_default=False,
        model_dump=lambda mode="python": {"decision_id": decision_id, "choice": choice, "answered_by": "user", "answered_at": now.isoformat()},
    )


def test_a_small_change_runs_from_request_to_a_delivered_report(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "state.db")
    over = _overrides(tmp_path, store, _Gateway({"modules": [_module("ledger", ["REQ-1"])]}), _Acceptance((True, [])))

    assert start_run(_request(), tmp_path, over) == RUN

    assert _status(store) == "DONE"
    kinds = _kinds(store)
    assert kinds[0] == "run_started" and kinds[-1] == "run_completed"
    (spec,) = over["scheduler"].specs
    assert spec.task_id == f"{RUN}-ledger" and spec.acceptance_test_refs == ["tests/test_ledger.py"]
    row = store.conn.execute("SELECT payload FROM tasks WHERE task_id = ?", (f"{RUN}-root",)).fetchone()
    assert row is not None
    completed = [json.loads(r["payload"]) for r in store.conn.execute("SELECT payload FROM outbox") if json.loads(r["payload"])["kind"] == "run_completed"][0]
    report = BlobStore(tmp_path / "blobs").get(completed["payload"]["report_ref"]).decode()
    assert "REQ-1: do REQ-1" in report and "Nothing was deployed" in report and "no decisions were needed" in report


def test_the_run_row_records_the_mode_and_a_budget(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "state.db")
    start_run(_request(), tmp_path, _overrides(tmp_path, store, _Gateway({"modules": [_module("ledger", ["REQ-1"])]}), _Acceptance((True, []))))
    payload = json.loads(store.conn.execute("SELECT payload FROM runs WHERE run_id = ?", (RUN,)).fetchone()["payload"])
    assert payload["mode"] == "impact" and payload["budget"]["max_task_nodes"] == 500 and payload["project_id"] == "p1"


def test_a_new_build_waits_for_plan_approval_and_resumes_after_the_answer(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "state.db")
    broker = DecisionBroker(store)
    over = _overrides(tmp_path, store, _Gateway({"modules": [_module("ledger", ["REQ-1"])]}), _Acceptance((True, [])), decision_broker=broker)

    start_run(_request("new_build"), tmp_path, over)
    assert _status(store) == "RUNNING" and [d.kind.value for d in broker.pending()] == ["approve_plan"]

    resume_run(RUN, tmp_path, over)  # not answered yet: nothing happens
    assert _status(store) == "RUNNING"

    broker.resolve(_answer(f"dec-plan-{RUN}", "approve"))
    resume_run(RUN, tmp_path, over)
    assert _status(store) == "DONE"
    over2_report = [json.loads(r["payload"]) for r in store.conn.execute("SELECT payload FROM outbox")][-1]
    assert "approve_plan" in BlobStore(tmp_path / "blobs").get(over2_report["payload"]["report_ref"]).decode()  # the decision log


def test_a_rejected_plan_cancels_the_run(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "state.db")
    broker = DecisionBroker(store)
    over = _overrides(tmp_path, store, _Gateway({"modules": [_module("ledger", ["REQ-1"])]}), _Acceptance((True, [])), decision_broker=broker)
    start_run(_request("new_build"), tmp_path, over)
    broker.resolve(_answer(f"dec-plan-{RUN}", "reject"))
    resume_run(RUN, tmp_path, over)
    assert _status(store) == "CANCELLED" and over["scheduler"].specs == []


def test_a_pause_command_stops_the_run_between_ticks(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "state.db")
    over = _overrides(tmp_path, store, _Gateway({"modules": [_module("ledger", ["REQ-1"])]}), _Acceptance((True, [])), control=lambda: "pause")
    over["driver"] = None
    start_run(_request(), tmp_path, over)
    assert _status(store) == "PAUSED"


def test_an_abort_command_cancels_the_run(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "state.db")
    over = _overrides(tmp_path, store, _Gateway({"modules": [_module("ledger", ["REQ-1"])]}), _Acceptance((True, [])), control=lambda: "abort")
    over["driver"] = None
    start_run(_request(), tmp_path, over)
    assert _status(store) == "CANCELLED"


def test_a_failed_root_fails_the_run(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "state.db")
    over = _overrides(tmp_path, store, _Gateway({"modules": [_module("ledger", ["REQ-1"])]}), _Acceptance((True, [])))
    over["driver"] = _driver(store, f"{RUN}-root", "ESCALATED")
    start_run(_request(), tmp_path, over)
    assert _status(store) == "FAILED"


def test_a_run_that_is_still_integrating_waits_instead_of_spinning(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "state.db")
    over = _overrides(tmp_path, store, _Gateway({"modules": [_module("ledger", ["REQ-1"])]}), _Acceptance((True, [])), max_ticks=3)
    over["driver"] = lambda: None
    start_run(_request(), tmp_path, over)
    assert _status(store) == "RUNNING"  # waiting; resumed later


def test_untraced_requirements_trigger_a_bounded_re_plan_of_just_those_requirements(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "state.db")
    gateway = _Gateway({"modules": [_module("ledger", ["REQ-1", "REQ-2"])]}, {"modules": [_module("audit", ["REQ-2"])]})
    acceptance = _Acceptance((False, ["REQ-2"]), (True, []))
    over = _overrides(tmp_path, store, gateway, acceptance)
    over["driver"] = lambda: _set_all(store, f"{RUN}-root", f"{RUN}-r1-root")

    start_run(_request(reqs=("REQ-1", "REQ-2")), tmp_path, over)

    assert _status(store) == "DONE" and len(acceptance.calls) == 2
    assert "REQ-1" in gateway.prompts[0] and "REQ-2" in gateway.prompts[0]
    assert "REQ-2" in gateway.prompts[1] and "REQ-1:" not in gateway.prompts[1]  # only the uncovered requirement is re-planned
    assert {s.task_id for s in over["scheduler"].specs} == {f"{RUN}-ledger", f"{RUN}-r1-audit"}


def test_acceptance_that_keeps_failing_ends_with_a_question_for_the_user(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "state.db")
    broker = DecisionBroker(store)
    gateway = _Gateway({"modules": [_module("ledger", ["REQ-1", "REQ-2"])]})
    acceptance = _Acceptance((False, ["REQ-2"]))
    over = _overrides(tmp_path, store, gateway, acceptance, decision_broker=broker)
    over["driver"] = lambda: _set_all(store, f"{RUN}-root", f"{RUN}-r1-root", f"{RUN}-r2-root")

    start_run(_request(reqs=("REQ-1", "REQ-2")), tmp_path, over)

    assert _status(store) == "AWAITING_DECISION" and len(acceptance.calls) == 3  # the first run plus two re-plan rounds
    (pending,) = broker.pending()
    assert pending.kind.value == "escalation" and "REQ-2" in pending.question and pending.evidence_refs == ["sha256:acceptance"]


def test_build_run_graph_compiles_without_a_checkpointer() -> None:
    assert build_run_graph(None) is not None


def test_in_a_git_repository_the_real_execution_wiring_is_built_without_calling_a_model(tmp_path: Path) -> None:
    import subprocess

    from asf.m3_orchestration.run_graph import default_components

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)  # noqa: S603, S607
    store = StateStore.open(tmp_path / "state.db")
    over = {"state_store": store, "gateway": _Gateway({"modules": []}), "blobs": BlobStore(tmp_path / "blobs")}

    c = default_components(tmp_path, RUN, over)

    assert type(c["scheduler"]).__name__ == "TaskScheduler" and type(c["workspace"]).__name__ == "Workspace"
    assert type(c["executor"]).__name__ == "ToolExecutor" and callable(c["driver"]) and callable(c["integrate"])
    assert c["gateway"] is over["gateway"] and c["project_root"] == str(tmp_path)
    assert c["scheduler"].dispatch_ready() == 0  # nothing queued, nothing started
    c["scheduler"].close()


def test_outside_a_git_repository_only_planning_collaborators_are_built(tmp_path: Path) -> None:
    from asf.m3_orchestration.run_graph import default_components

    store = StateStore.open(tmp_path / "state.db")
    c = default_components(tmp_path, RUN, {"state_store": store, "blobs": BlobStore(tmp_path / "blobs")})
    assert "scheduler" not in c and "driver" not in c
    assert c["control"]() is None  # no commands queued
