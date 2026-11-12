# FILE: src/asf/m4_execution/integration/integrator.py
# ROLE: Bottom-up integration: when all children are done, run integration tests on the parent branch, repair or publish RootIntegrated.
# ARCH REF: M4; p08 Integration & Repair; IF-09 repair tasks; IF-10c RootIntegrated
# OWNS: Integration runs and parent promotion
# DOES NOT OWN: Leaf gates
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/outcomes.py: RootIntegrated, TaskOutcome (IF-10c, escalation)
#   - imports from src/asf/m4_execution/integration/repair.py: make_repair_task (repair)
#   - imports from src/asf/m4_execution/scheduler.py: TaskScheduler (IF-09 repair tasks)
#   - imports from src/asf/m5_shared/workspace/workspace.py: Workspace (IF-15 git operations)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (IF-16 state)
#   - imports from src/asf/contracts/contract_spec.py: ContractStatus (contracts become STABLE)
#   - imports from src/asf/contracts/state.py: StateCommit (task transitions plus events)
#   - imports from src/asf/contracts/tasks.py: LeafTaskSpec, TaskNode (repair leaf)
#   - called by tests/m4_execution/integration/test_integrator.py: build_integration_graph, integrate_parent
#   - emits/consumes: emits GATE_RESULT for integration tests and STATE_CHANGED INTEGRATED
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Build the graph with LangGraph StateGraph; side-effecting steps use the Functional API @task so they are not re-run on resume (D-04).
#   6. Nodes must be idempotent up to any interrupt(): write the DecisionRequest through DecisionBroker first, then call interrupt() (D-06).
#   7. Pass thread_id = the run or node id; use the SqliteSaver from checkpoints.db with durability="sync" (D-05).
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m4_execution/integration/test_integrator.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m4_execution/integration/integrator.py` and `uv run mypy src/asf/m4_execution/integration/integrator.py` are clean.

import json
import logging
import re
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict, cast

from langgraph.config import get_config
from langgraph.graph import END, START, StateGraph

from asf.contracts.contract_spec import ContractStatus
from asf.contracts.outcomes import RootIntegrated, TaskOutcome
from asf.contracts.state import StateCommit
from asf.contracts.tasks import LeafTaskSpec, TaskNode
from asf.m4_execution.integration.repair import make_repair_task
from asf.m4_execution.scheduler import TaskScheduler
from asf.m5_shared.state_store.store import StateStore
from asf.m5_shared.workspace.workspace import Workspace

logger = logging.getLogger(__name__)

INTEGRATION_TIMEOUT_S = 900
DEFAULT_TEST_COMMAND = ["uv", "run", "pytest", "-q", "--no-header"]
_DONE = ("VERIFIED", "INTEGRATED")
_FAILED_TEST = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.MULTILINE)

Runner = Callable[[list[str], Path, int], Any]


class IntegrationState(TypedDict, total=False):
    parent_id: str
    children_done: bool
    green: bool
    report_ref: str
    failing_tests: list[str]
    result: Any
    note: str


def _dependency(name: str) -> Any:
    """Live collaborators come from ``config["configurable"]`` (they cannot be checkpointed)."""
    return get_config().get("configurable", {}).get(name)


def _require(name: str) -> Any:
    value = _dependency(name)
    if value is None:
        raise RuntimeError(f"the integration graph needs '{name}' in config['configurable']")
    return value


def _event(run_id: str, task_id: str, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": f"evt-{uuid.uuid4().hex}",
        "run_id": run_id,
        "task_id": task_id,
        "seq": 0,
        "ts": datetime.now(UTC).isoformat(),
        "actor": {"kind": "service", "role": "integrator", "name": "Integrator"},
        "kind": kind,
        "correlation_id": run_id,
        "payload": payload,
    }


def _task_row(store: StateStore, task_id: str) -> tuple[int, dict[str, Any]]:
    row = store.conn.execute("SELECT version, payload FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if row is None:
        raise KeyError(f"Task not found: {task_id}")
    return int(row["version"]), json.loads(row["payload"] or "{}")


def _transition(store: StateStore, node: TaskNode, state: str, extra: dict[str, Any] | None = None, events: list[dict[str, Any]] | None = None) -> None:
    """Move a task to a new state with its STATE_CHANGED event in one commit (optimistic concurrency)."""
    version, payload = _task_row(store, str(node.id))
    previous = str(payload.get("state", node.state))
    change = {
        "entity": "task",
        "entity_id": str(node.id),
        "expected_version": version,
        "mutation": {"state": state, "prior_state": previous, **(extra or {})},
        "events": [_event(str(node.run_id), str(node.id), "state_changed", {"entity": "task", "from": previous, "to": state}), *(events or [])],
    }
    store.commit(StateCommit.model_validate(change))


def _children(store: StateStore, parent_id: str) -> list[tuple[str, str, dict[str, Any]]]:
    rows = store.conn.execute("SELECT task_id, state, payload FROM tasks WHERE parent_id = ? ORDER BY rowid", (parent_id,)).fetchall()
    return [(str(r["task_id"]), str(r["state"]), json.loads(r["payload"] or "{}")) for r in rows]


def _localise(failing: list[str], children: list[tuple[str, str, dict[str, Any]]]) -> list[str]:
    """Failing tests -> the child (and files) that own them, using acceptance refs and allowed-file names."""
    owners: list[str] = []
    for test_id in failing:
        test_stem = Path(test_id.split("::")[0]).stem.removeprefix("test_")
        for child_id, _state, payload in children:
            refs = [str(r) for r in payload.get("acceptance_refs", [])]
            files = [Path(str(f)).stem for f in payload.get("allowed_files", [])]
            if any(test_id.split("::")[0] in r for r in refs) or test_stem in files:
                owners.append(child_id)
    return list(dict.fromkeys(owners))


def _node_check_children(state: IntegrationState) -> dict[str, Any]:
    store: StateStore = _require("state_store")
    kids = _children(store, state["parent_id"])
    return {"children_done": bool(kids) and all(s in _DONE for _, s, _ in kids)}


def _node_integrate(state: IntegrationState) -> dict[str, Any]:
    store: StateStore = _require("state_store")
    workspace: Workspace = _require("workspace")
    runner: Runner = _require("test_runner")
    command: list[str] = list(_dependency("test_command") or DEFAULT_TEST_COMMAND)
    parent = store.get_task(state["parent_id"])
    _transition(store, parent, "INTEGRATING")

    result = runner(command, workspace.repo_dir, INTEGRATION_TIMEOUT_S)
    log = (result.stdout + b"\n" + result.stderr).decode("utf-8", errors="replace")
    green = result.exit_code == 0 and not result.timed_out
    report_ref = workspace.blobs.put(log.encode("utf-8"))
    failing = list(dict.fromkeys(_FAILED_TEST.findall(log)))

    version, _ = _task_row(store, state["parent_id"])
    store.commit(
        StateCommit.model_validate(
            {
                "entity": "task",
                "entity_id": state["parent_id"],
                "expected_version": version,
                "mutation": {},
                "events": [_event(str(parent.run_id), state["parent_id"], "gate_result", {"passed": green, "summary": "integration tests", "report_ref": report_ref})],
            }
        )
    )
    return {"green": green, "report_ref": report_ref, "failing_tests": failing}


def _node_promote(state: IntegrationState) -> dict[str, Any]:
    store: StateStore = _require("state_store")
    parent = store.get_task(state["parent_id"])
    _transition(store, parent, "INTEGRATED")

    registry = _dependency("registry")
    if registry is not None:
        for contract_ref in parent.contract_refs:
            registry.promote(contract_ref.split("@")[0], ContractStatus.STABLE)  # DRAFT/VERIFIED -> STABLE once integrated

    if parent.parent_id is None:
        done = RootIntegrated.model_validate({"run_id": str(parent.run_id), "root_task": str(parent.id), "report_ref": state["report_ref"]})
        return {"result": done}

    scheduler: TaskScheduler | None = _dependency("scheduler")
    if scheduler is not None:
        scheduler.mark_verified(str(parent.id))  # the parent now counts as a verified child of its own parent
    return {"note": f"{parent.id} integrated; its parent is next"}


def _node_repair(state: IntegrationState) -> dict[str, Any]:
    store: StateStore = _require("state_store")
    workspace: Workspace = _require("workspace")
    scheduler: TaskScheduler | None = _dependency("scheduler")
    outcome_sink = _dependency("outcome_sink")
    parent = store.get_task(state["parent_id"])
    owners = _localise(state.get("failing_tests", []), _children(store, state["parent_id"]))

    repair = make_repair_task(parent, state["report_ref"], parent.counters.repair_rounds)
    if repair is None:
        _transition(store, parent, "ESCALATED")
        if outcome_sink is not None:
            outcome_sink(
                TaskOutcome.model_validate(
                    {"task_id": str(parent.id), "failure_class": "ESCALATED", "evidence_ref": state["report_ref"], "attempts": parent.counters.repair_rounds}
                )
            )
        return {"note": "repair rounds exhausted; escalated"}

    counters = parent.counters.model_copy(update={"repair_rounds": parent.counters.repair_rounds + 1}).model_dump()
    _transition(store, parent, "REPAIRING", {"counters": counters})
    if scheduler is not None:
        code, head, _ = workspace._run_git(["rev-parse", "HEAD"])
        spec = LeafTaskSpec.model_validate(
            {
                "task_id": str(repair.id),
                "goal": repair.goal,
                "acceptance_test_refs": state.get("failing_tests", []) or repair.acceptance_refs,
                "capsules": [],
                "allowed_files": repair.allowed_files,
                "context_budget_tokens": 8000,
                "base_commit": head if code == 0 else "HEAD",
                "parent_branch": f"task/{parent.id}",
            }
        )
        scheduler.enqueue(spec)
    return {"note": f"repair {repair.id} queued for {', '.join(owners) or 'the subtree'}"}


def build_integration_graph(checkpointer: Any) -> Any:
    """Compile the integration graph. Collaborators are passed in ``config["configurable"]``:
    state_store, workspace, test_runner (and optionally registry, scheduler, outcome_sink, test_command)."""
    builder = StateGraph(IntegrationState)
    builder.add_node("check_children", _node_check_children)
    builder.add_node("integrate", _node_integrate)
    builder.add_node("promote", _node_promote)
    builder.add_node("repair", _node_repair)

    builder.add_edge(START, "check_children")
    builder.add_conditional_edges("check_children", lambda s: "integrate" if s.get("children_done") else END, {"integrate": "integrate", END: END})
    builder.add_conditional_edges("integrate", lambda s: "promote" if s.get("green") else "repair", {"promote": "promote", "repair": "repair"})
    builder.add_edge("promote", END)
    builder.add_edge("repair", END)
    return builder.compile(checkpointer=checkpointer) if checkpointer is not None else builder.compile()


def integrate_parent(
    task_id: str,
    *,
    state_store: StateStore,
    workspace: Workspace,
    test_runner: Runner,
    registry: Any = None,
    scheduler: TaskScheduler | None = None,
    outcome_sink: Callable[[Any], None] | None = None,
    test_command: list[str] | None = None,
    checkpointer: Any = None,
) -> RootIntegrated | None:
    """Integrate ``task_id`` when all its children are done. Returns RootIntegrated for a green root, else None."""
    graph = build_integration_graph(checkpointer)
    configurable: dict[str, Any] = {
        "thread_id": f"integrate-{task_id}",
        "state_store": state_store,
        "workspace": workspace,
        "test_runner": test_runner,
        "registry": registry,
        "scheduler": scheduler,
        "outcome_sink": outcome_sink,
        "test_command": test_command,
    }
    output = graph.invoke({"parent_id": task_id}, {"configurable": configurable})
    result = cast(Mapping[str, Any], output).get("result")
    return result if isinstance(result, RootIntegrated) else None
