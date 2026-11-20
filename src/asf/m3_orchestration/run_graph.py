# FILE: src/asf/m3_orchestration/run_graph.py
# ROLE: Main Orchestrator: the durable run graph from StructuredRequest to final acceptance and report.
# ARCH REF: M3; p01 HLD; p04 Main Orchestrator; p13 SEQ-1 happy path; p14 SEQ-2 recovery; IF-02; IF-10b; IF-10c; D-04; D-05; D-06
# OWNS: Run lifecycle, budgets, mode selection, re-plan loop, final acceptance
# DOES NOT OWN: Decomposition (decomposition_graph); execution (M4)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/requests.py: StructuredRequest (IF-02)
#   - imports from src/asf/contracts/outcomes.py: DecompositionReport, RootIntegrated (IF-10b/IF-10c)
#   - imports from src/asf/contracts/budget.py: RunBudget (budgets)
#   - imports from src/asf/m3_orchestration/planning/planner_graph.py: build_planner_graph (planning)
#   - imports from src/asf/m3_orchestration/decomposition/decomposition_graph.py: build_decomposition_graph (decomposition)
#   - imports from src/asf/m3_orchestration/acceptance.py: final_acceptance (final gate)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (IF-16 state)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (IF-03 decisions)
#   - imports from src/asf/config/paths.py: get_paths (state.db and checkpoints.db locations)
#   - imports from src/asf/contracts/decisions.py: DecisionRequest (the acceptance escalation request)
#   - imports from src/asf/contracts/ids.py: new_id (run and event ids)
#   - imports from src/asf/contracts/models.py: ModelProfile (the default calibrated profile)
#   - imports from src/asf/contracts/state.py: StateCommit (run and task commits)
#   - imports from src/asf/m3_orchestration/decomposition/frontier.py: Frontier (the persisted work-list)
#   - imports from src/asf/m3_orchestration/escalation.py: handle_escalation (outcomes from the scheduler)
#   - imports from src/asf/m3_orchestration/planning/modes.py: select_mode (the run mode)
#   - imports from src/asf/m3_orchestration/run_control.py: RunSupervisor (pause / abort commands)
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (the delivered report)
#   - imports from src/asf/m4_execution/scheduler.py: TaskScheduler (dispatch of certified leaves)
#   - imports from src/asf/m4_execution/verification/gate.py: verify_change_set, run_in_sandbox (the gate after each attempt)
#   - imports from src/asf/m4_execution/worker/worker_graph.py: run_attempt (one worker attempt)
#   - imports from src/asf/m4_execution/integration/integrator.py: integrate_parent (bottom-up integration)
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (model routing)
#   - imports from src/asf/m5_shared/runtime/local_runtime.py: LocalRuntime (slot leases)
#   - imports from src/asf/m5_shared/tools/builtin_tools.py: register_builtin_tools (tools for the worker)
#   - imports from src/asf/m5_shared/tools/executor.py: ToolExecutor (tool calls)
#   - imports from src/asf/m5_shared/tools/registry.py: ToolRegistry (tool registry)
#   - imports from src/asf/m5_shared/workspace/workspace.py: Workspace (git worktrees)
#   - imports from src/asf/m5_shared/events/event_log.py: EventLog (the log the relay feeds)
#   - imports from src/asf/contracts/contract_spec.py: ContractQuery (the pinned contracts the test author is shown)
#   - imports from src/asf/m5_shared/registry/registry.py: ContractRegistry (the plan's interfaces reach the workers as capsules)
#   - imports from src/asf/m5_shared/state_store/outbox.py: OutboxRelay (committed events reach the event log)
#   - imports from src/asf/m3_orchestration/planning/test_authoring.py: author_acceptance_tests (acceptance tests written by the planner tier)
#   - imports from src/asf/m5_shared/memory/hooks.py: MemoryHooks (project memory around attempts)
#   - called by src/asf/cli/commands/run.py: start_run, resume_run
#   - called by tests/m3_orchestration/test_run_graph.py: build_run_graph, start_run, resume_run
#   - called by tests/m3_orchestration/test_e2e.py: start_run
#   - imports from src/asf/m5_shared/trace.py: start_trace, trace_event (the run's flight recorder starts here)
#   - imports from src/asf/m5_shared/gateway/usage_callback.py: drain_call_metrics (model calls queued by any thread are written to call_metrics here)
#   - emits/consumes: emits RUN_STARTED, RUN_COMPLETED, emits narrative events TASK_RECEIVED, STEP_STARTED, HANDOFF_SENT, HANDOFF_RECEIVED, GATE_RESULT, DECISION_NEEDED (with causation_id set to the triggering event) via StateStore.commit
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Build the graph with LangGraph StateGraph; side-effecting steps use the Functional API @task so they are not re-run on resume (D-04).
#   6. Nodes must be idempotent up to any interrupt(): write the DecisionRequest through DecisionBroker first, then call interrupt() (D-06).
#   7. Pass thread_id = the run or node id; use the SqliteSaver from checkpoints.db with durability="sync" (D-05).
#   8. Re-plan uncovered requirements at most 2 rounds, then HITL.
#   9. Never deploy; deliver a report only.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/test_run_graph.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/run_graph.py` and `uv run mypy src/asf/m3_orchestration/run_graph.py` are clean.

import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

from langgraph.config import get_config
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from asf.config.paths import get_paths
from asf.contracts.budget import RunBudget
from asf.contracts.contract_spec import ContractQuery
from asf.contracts.decisions import DecisionRequest
from asf.contracts.ids import new_id
from asf.contracts.models import ModelProfile
from asf.contracts.outcomes import DecompositionReport, RootIntegrated  # noqa: F401
from asf.contracts.requests import StructuredRequest
from asf.contracts.state import StateCommit
from asf.m3_orchestration.acceptance import final_acceptance
from asf.m3_orchestration.decomposition.decomposition_graph import build_decomposition_graph
from asf.m3_orchestration.decomposition.frontier import Frontier
from asf.m3_orchestration.escalation import handle_escalation
from asf.m3_orchestration.planning.modes import select_mode
from asf.m3_orchestration.planning.planner_graph import build_planner_graph, plan_result
from asf.m3_orchestration.run_control import RunSupervisor
from asf.m5_shared.decisions.broker import DecisionBroker
from asf.m5_shared.events.event_log import EventLog
from asf.m5_shared.registry.registry import ContractRegistry
from asf.m5_shared.state_store.outbox import OutboxRelay
from asf.m5_shared.state_store.store import StateStore
from asf.m5_shared.trace import start_trace, trace_event
from asf.m5_shared.workspace.blobs import BlobStore

logger = logging.getLogger(__name__)

MAX_REPLAN_ROUNDS = 2
POLL_INTERVAL_S = 0.5
_DONE_TASK_STATES = ("VERIFIED", "INTEGRATED")
_FAILED_ROOT_STATES = ("ESCALATED", "ABANDONED", "CANCELLED")
_AGENT_NAMES = {"planner": "Planner", "decomposer": "Decomposer", "worker": "Worker", "gate": "Gate", "integrator": "Integrator", "reviewer": "Reviewer"}

Driver = Callable[[], dict[str, Any] | None]


class RunState(TypedDict, total=False):
    request: dict[str, Any]
    run_id: str
    project_root: str
    plan: dict[str, Any] | None
    decomposition: dict[str, Any]
    replan_rounds: int
    untraced: list[str]
    acceptance: dict[str, Any]
    status: str
    report_ref: str
    note: str


def _dep(name: str, default: Any = None) -> Any:
    value = get_config().get("configurable", {}).get(name)
    return default if value is None else value


def _event(run_id: str, kind: str, payload: dict[str, Any], task_id: str | None = None) -> dict[str, Any]:
    return {
        "event_id": f"evt-{new_id('e')}",
        "run_id": run_id,
        "task_id": task_id,
        "seq": 0,
        "ts": datetime.now(UTC).isoformat(),
        "actor": {"kind": "service", "role": "orchestrator", "name": "Main orchestrator"},
        "kind": kind,
        "correlation_id": run_id,
        "payload": payload,
    }


def _say(run_id: str, role: str, kind: str, payload: dict[str, Any], task_id: str | None = None, caused_by: str | None = None) -> str | None:
    """Record one narrative event (who did what, hand-offs) for the web viewer and `factory trace`; returns its event id.

    Narration is advisory: a failure to record it is logged and never stops the run. Main thread only (the state store is thread-bound).
    """
    store: StateStore | None = _dep("state_store")
    if store is None:
        return None
    try:
        event = _event(run_id, kind, payload, task_id)
        event["actor"] = {"kind": "agent", "role": role, "name": _AGENT_NAMES.get(role, role.title())}
        if caused_by:
            event["causation_id"] = caused_by
        row = store.conn.execute("SELECT version, status FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        store.commit(
            StateCommit.model_validate(
                {"entity": "run", "entity_id": run_id, "expected_version": int(row["version"]), "mutation": {"status": row["status"]}, "events": [event]}
            )
        )
        trace_event("narrative", kind, role=role, task=task_id, payload=payload, caused_by=caused_by)
        _relay()  # so the viewer sees the line now, not when the monitor next ticks
        return str(event["event_id"])
    except Exception:  # noqa: BLE001 - the story is an aid; the run goes on without a line of it
        logger.warning("could not record a %s narrative event", kind, exc_info=True)
        return None


def _hand_off(run_id: str, sender: str, receiver: str, summary: str, task_id: str | None = None) -> None:
    """A hand-off is a pair of events: the sender's HANDOFF_SENT and the receiver's HANDOFF_RECEIVED caused by it."""
    sent = _say(run_id, sender, "handoff_sent", {"to_role": receiver, "summary": summary}, task_id)
    _say(run_id, receiver, "handoff_received", {"summary": summary}, task_id, caused_by=sent)


def _spec_file(project_root: Path, task_id: str) -> Path:
    return project_root / ".factory" / "specs" / f"{task_id}.json"


def _restore_specs(project_root: Path, store: StateStore, scheduler: Any) -> int:
    """Re-queue the leaves a previous process certified but did not finish (a resumed run used to wait for them forever)."""
    if getattr(scheduler, "enqueue_json", None) is None:
        return 0
    restored = 0
    for row in store.conn.execute("SELECT task_id FROM tasks WHERE state IN ('LEAF_CERTIFIED', 'READY', 'BLOCKED')").fetchall():
        task_id = str(row["task_id"])
        saved = _spec_file(project_root, task_id)
        if scheduler.state_of(task_id) is None and saved.is_file():
            scheduler.enqueue_json(saved.read_text(encoding="utf-8"))
            restored += 1
    return restored


def _flush_metrics() -> None:
    """Write the model calls queued since the last look into call_metrics, on this thread with the run's own connection."""
    from asf.m5_shared.gateway.usage_callback import drain_call_metrics  # langchain_core: loaded when a model has been built, not before

    store: StateStore | None = _dep("state_store")
    rows = drain_call_metrics()
    if store is None or not rows:
        return
    try:
        with store.conn:
            store.conn.executemany(
                "INSERT INTO call_metrics (run_id, task_id, provider, model, input_tokens, output_tokens, cost, duration_ms, timestamp, role, strategy, estimated, retry_no) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
    except Exception:  # noqa: BLE001 - metrics are an aid; the run goes on
        logger.warning("could not write %d call metrics", len(rows), exc_info=True)


def _relay() -> None:
    """Move committed outbox rows into the event log so the trace, dashboard and web viewer can read them."""
    _flush_metrics()
    relay: OutboxRelay | None = _dep("relay")
    if relay is not None:
        relay.relay_once()


def _set_status(store: StateStore, run_id: str, status: str, kind: str | None = None, payload: dict[str, Any] | None = None) -> None:
    """Commit the run's status (and optionally one event) in a single transaction."""
    row = store.conn.execute("SELECT version FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    events = [_event(run_id, kind, {"status": status, **(payload or {})})] if kind else []
    store.commit(
        StateCommit.model_validate(
            {"entity": "run", "entity_id": run_id, "expected_version": int(row["version"]) if row else None, "mutation": {"status": status}, "events": events}
        )
    )
    _relay()


# -- nodes -----------------------------------------------------------------------------------------------------------


def _node_create_run(state: RunState) -> dict[str, Any]:
    store: StateStore = _dep("state_store")
    run_id = state["run_id"]
    request = StructuredRequest.model_validate(state["request"])
    if store.conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)).fetchone() is None:  # idempotent on resume
        budget: RunBudget = _dep("budget") or _default_budget(run_id)
        store.commit(
            StateCommit.model_validate(
                {
                    "entity": "run",
                    "entity_id": run_id,
                    "expected_version": None,
                    "mutation": {
                        "project_id": str(request.project_id),
                        "status": "RUNNING",
                        "request_id": request.request_id,
                        "mode": select_mode(request).value,
                        "budget": budget.model_dump(mode="json"),
                        "profile": str(_dep("profile_name") or ""),  # `factory run resume` must use the profile the run started with
                    },
                    "events": [_event(run_id, "run_started", {"request_id": request.request_id, "mode": select_mode(request).value})],
                }
            )
        )
        _relay()
    return {"status": "RUNNING", "replan_rounds": state.get("replan_rounds", 0)}


def _default_budget(run_id: str) -> RunBudget:
    return RunBudget.model_validate(
        {
            "run_id": run_id,
            "max_remote_tokens": 2_000_000,
            "max_local_tokens": 20_000_000,
            "max_api_spend": 20.0,
            "max_wall_clock_s": 6 * 3600,
            "max_task_nodes": 500,
        }
    )


def _node_plan(state: RunState) -> dict[str, Any]:
    request = state["request"]
    if state.get("untraced"):  # a re-plan covers only what the final acceptance found untraced
        wanted = set(state["untraced"])
        request = {**request, "requirements": [r for r in request["requirements"] if r["req_id"] in wanted]}
    rid = state["run_id"]
    goals = [str(r.get("text", "")).strip() for r in request.get("requirements", []) if str(r.get("text", "")).strip()]
    _say(rid, "planner", "task_received", {"goal_summary": (goals[0] if goals else "the request") + f" (+{max(0, len(goals) - 1)} more requirements)", "from_role": "user"})
    _say(rid, "planner", "step_started", {"step_no": 1, "strategy": "plan_then_verify", "summary": f"designing modules for {len(goals)} requirements"})
    planner = build_planner_graph(None)
    out = planner.invoke({"request": request, "run_id": f"{state['run_id']}-r{state.get('replan_rounds', 0)}" if state.get("untraced") else state["run_id"]}, get_config())
    approved = plan_result(out)
    if approved is None:
        _set_status(_dep("state_store"), state["run_id"], "CANCELLED", "run_completed", {"reason": "the plan was rejected"})
        return {"plan": None, "status": "CANCELLED", "note": "the plan was rejected"}
    modules = [str(n.id).rsplit("-", 1)[-1] for n in [*approved.shared_type_nodes, *approved.module_nodes]]
    _hand_off(rid, "planner", "decomposer", f"design plan approved: {', '.join(modules) or 'no modules'}")
    return {"plan": approved.model_dump(mode="json"), "status": "RUNNING"}


def _after_plan(state: RunState) -> str:
    return "decompose" if state.get("plan") else "end"


def _persist_root(store: StateStore, plan: dict[str, Any]) -> None:
    root = dict(plan["root"])
    if store.conn.execute("SELECT 1 FROM tasks WHERE task_id = ?", (root["id"],)).fetchone() is None:
        store.commit(StateCommit.model_validate({"entity": "task", "entity_id": root["id"], "expected_version": None, "mutation": {**root, "state": "DECOMPOSED"}}))


def _node_decompose(state: RunState) -> dict[str, Any]:
    store: StateStore = _dep("state_store")
    plan = state["plan"]
    assert plan is not None
    if store.conn.execute("SELECT 1 FROM tasks WHERE task_id = ?", (plan["root"]["id"],)).fetchone() is None:
        _persist_root(store, plan)
    graph = build_decomposition_graph(None)
    request = StructuredRequest.model_validate(state["request"])
    out = graph.invoke({"plan": plan, "requirement_ids": [r.req_id for r in request.requirements]}, get_config())
    report = DecompositionReport.model_validate(out["report"])
    _dep("leaf_ids", set()).update(out.get("leaves", []))
    rid = state["run_id"]
    titles = {str(r["task_id"]): str(r["title"]) for r in store.conn.execute("SELECT task_id, title FROM tasks WHERE run_id = ?", (rid,))}
    leaves = [str(x) for x in out.get("leaves", [])]
    _say(rid, "decomposer", "step_started", {"step_no": 2, "strategy": "recursive_split", "summary": f"{len(titles)} tasks, {len(leaves)} ready for a worker"})
    for leaf in leaves:
        _hand_off(rid, "decomposer", "worker", titles.get(leaf, leaf)[:160], leaf)
    for task_id in out.get("suspended", []) or []:
        _say(rid, "decomposer", "decision_needed", {"kind": "clarify", "question": titles.get(str(task_id), str(task_id))[:200] + " needs an answer before it can be split"}, str(task_id))
    return {"decomposition": report.model_dump(mode="json")}


_PROGRESS_LINES = {
    "RUNNING": ("worker", "step_started", "working on"),
    "VERIFYING": ("gate", "step_started", "verifying"),
    "VERIFIED": ("gate", "gate_result", "passed"),
    "FAILED_ATTEMPT": ("gate", "gate_result", "failed"),
    "REPAIRING": ("integrator", "step_started", "repairing"),
    "INTEGRATING": ("integrator", "step_started", "integrating"),
    "INTEGRATED": ("integrator", "step_started", "integrated"),
    "ESCALATED": ("worker", "decision_needed", "could not finish"),
}


def _narrate_progress(store: StateStore, run_id: str, seen: dict[str, str]) -> None:
    """One narrative line per task whose state changed since the last look: the worker starts, the gate verdict, integration."""
    try:
        rows = store.conn.execute("SELECT task_id, state, title FROM tasks WHERE run_id = ?", (run_id,)).fetchall()
    except Exception:  # noqa: BLE001 - narration only
        return
    for row in rows:
        task_id, now = str(row["task_id"]), str(row["state"])
        if seen.get(task_id) == now:
            continue
        seen[task_id] = now
        line = _PROGRESS_LINES.get(now)
        if line is None:
            continue
        role, kind, verb = line
        title = str(row["title"])[:140]
        if kind == "gate_result":
            payload: dict[str, Any] = {"passed": now == "VERIFIED", "summary": title}
        elif kind == "decision_needed":
            payload = {"kind": "escalation", "question": f"{title} ({verb})"}
        else:
            payload = {"step_no": 1, "strategy": role, "summary": f"{verb} {title}"}
        _say(run_id, role, kind, payload, task_id)


def _answered_nodes(store: StateStore, run_id: str) -> tuple[list[str], list[str]]:
    """Nodes parked on a decomposer question (cannot be split, too ambiguous) whose answer has arrived: (certify as leaf, abandon)."""
    accept: list[str] = []
    abandon: list[str] = []
    rows = store.conn.execute("SELECT task_id, payload FROM decisions WHERE run_id = ? AND status = 'RESOLVED' AND topic IN ('manual_split', 'clarify', 'escalation')", (run_id,)).fetchall()
    for row in rows:
        task_id = str(row["task_id"] or "")
        state_row = store.conn.execute("SELECT state FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if not task_id or state_row is None or str(state_row["state"]) not in ("ESCALATED", "AWAITING_INPUT"):
            continue  # already applied, or not parked
        choice = str(json.loads(row["payload"]).get("resolution", {}).get("choice", ""))
        if choice in ("accept_larger_leaf", "clarified", "replan"):  # replan: the task is tried again (the help ladder gives it the bigger models)
            accept.append(task_id)
        elif choice == "abandon_subtree":
            abandon.append(task_id)
    return accept, abandon


_ACTIVE_STATES = ("PROPOSED", "SIZING", "SPLITTING", "READY", "RUNNING", "VERIFYING", "REPAIRING", "ESCALATED", "AWAITING_INPUT", "FAILED_ATTEMPT")


def _stuck_behind_abandoned(store: StateStore, run_id: str) -> bool:
    """True when something was abandoned, nothing is running or waiting for an answer, and the tasks left cannot start: the run would idle for ever."""
    states = {str(r[0]) for r in store.conn.execute("SELECT DISTINCT state FROM tasks WHERE run_id = ?", (run_id,))}
    if "ABANDONED" not in states or states & set(_ACTIVE_STATES):
        return False
    pending = store.conn.execute("SELECT COUNT(*) FROM decisions WHERE run_id = ? AND status = 'PENDING'", (run_id,)).fetchone()
    return not (pending and int(pending[0]))


def _root_state(store: StateStore, root_id: str) -> str | None:
    row = store.conn.execute("SELECT state FROM tasks WHERE task_id = ?", (root_id,)).fetchone()
    return str(row["state"]) if row is not None else None


def _node_monitor(state: RunState) -> dict[str, Any]:
    """Drive execution until the root is integrated (RootIntegrated), the run is paused or cancelled, or the root fails."""
    store: StateStore = _dep("state_store")
    plan = state["plan"]
    assert plan is not None
    root_id = plan["root"]["id"]
    driver: Driver | None = _dep("driver")
    control: Callable[[], str | None] | None = _dep("control")
    sleep: Callable[[float], None] = _dep("sleep", time.sleep)
    max_ticks = _dep("max_ticks")
    ticks = 0
    seen: dict[str, str] = {}
    applied: set[str] = set()

    while True:
        command = control() if control is not None else None
        if command == "pause":
            _set_status(store, state["run_id"], "PAUSED", "state_changed")
            interrupt({"paused": True, "run_id": state["run_id"]})  # the run waits here until `factory run resume`
            _set_status(store, state["run_id"], "RUNNING", "state_changed")
            continue
        trace_event("run", "tick", tick=ticks, control=command, states=dict(seen))
        if command == "abort":
            _set_status(store, state["run_id"], "CANCELLED", "cancelled")
            return {"status": "CANCELLED", "note": "aborted by the user"}

        accept, abandon = _answered_nodes(store, state["run_id"])
        # an answer is applied once per process: the task escalates again after the accepted attempt, its old answer is still RESOLVED, and
        # applying it on every tick re-opened the task about eighty times (a run that never ended and spent tokens for nothing)
        accept = [t for t in accept if t not in applied]
        abandon = [t for t in abandon if t not in applied]
        applied.update(accept, abandon)
        for task_id in abandon:
            row = store.conn.execute("SELECT version FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is not None:
                store.commit(StateCommit.model_validate({"entity": "task", "entity_id": task_id, "expected_version": int(row["version"]), "mutation": {"state": "ABANDONED"}}))
                trace_event("run", "subtree_abandoned", task=task_id)
        if accept:
            trace_event("run", "answers_applied", accept=accept)
            out = build_decomposition_graph(None).invoke({"plan": plan, "force_leaf": accept, "requirement_ids": []}, get_config())
            _dep("leaf_ids", set()).update(out.get("leaves", []))
        _restore_specs(Path(state["project_root"]), store, _dep("scheduler"))  # a leaf certified by a process that stopped is queued again
        requests = driver() if driver is not None else None
        _relay()
        _narrate_progress(store, state["run_id"], seen)
        if requests and (requests.get("resplit") or requests.get("woken")):
            graph = build_decomposition_graph(None)
            out = graph.invoke({"plan": plan, "resplit": requests.get("resplit", {}), "requirement_ids": []}, get_config())
            _dep("leaf_ids", set()).update(out.get("leaves", []))
        
        current = _root_state(store, root_id)
        if current == "INTEGRATED":
            return {"status": "RUNNING", "note": "root integrated"}
        if current in _FAILED_ROOT_STATES:
            _set_status(store, state["run_id"], "FAILED", "run_completed", {"reason": f"the root task is {current}"})
            return {"status": "FAILED", "note": f"the root task is {current}"}

        if _stuck_behind_abandoned(store, state["run_id"]):
            reason = "the remaining work depends on abandoned tasks; the run ends here with what was verified, and the delivery report lists what is missing"
            trace_event("run", "stuck_behind_abandoned", run=state["run_id"])
            _set_status(store, state["run_id"], "FAILED", "run_completed", {"reason": reason})
            return {"status": "FAILED", "note": reason}

        ticks += 1
        if max_ticks is not None and ticks >= int(max_ticks):
            return {"status": "WAITING", "note": "still integrating; the run continues when resumed"}
        sleep(POLL_INTERVAL_S)


def _after_monitor(state: RunState) -> str:
    return "acceptance" if state.get("status") == "RUNNING" else "end"


def _node_acceptance(state: RunState) -> dict[str, Any]:
    request = StructuredRequest.model_validate(state["request"])
    root = Path(state["project_root"])
    acceptance = _dep("acceptance") or final_acceptance
    result = acceptance(request, root, regression=_dep("regression"), blobs=_dep("blobs"))
    _say(state["run_id"], "gate", "gate_result", {"passed": bool(result.passed), "summary": f"final acceptance, {len(result.untraced)} requirement(s) untraced"})
    return {"acceptance": result.model_dump(mode="json"), "untraced": list(result.untraced)}


def _after_acceptance(state: RunState) -> str:
    result = state["acceptance"]
    if result["passed"]:
        return "report"
    if result["untraced"] and state.get("replan_rounds", 0) < MAX_REPLAN_ROUNDS:
        return "replan"
    return "ask_user"


def _node_replan(state: RunState) -> dict[str, Any]:
    return {"replan_rounds": state.get("replan_rounds", 0) + 1}


def _node_ask_user(state: RunState) -> dict[str, Any]:
    store: StateStore = _dep("state_store")
    broker: DecisionBroker | None = _dep("decision_broker")
    result = state["acceptance"]
    detail = f"untraced requirements: {result['untraced']}; failing tests: {result['failing_tests']}"
    if broker is not None:
        broker.request(
            DecisionRequest.model_validate(
                {
                    "decision_id": f"dec-acceptance-{state['run_id']}",
                    "run_id": state["run_id"],
                    "kind": "escalation",
                    "requester": "asf.m3_orchestration.run_graph",
                    "question": f"Final acceptance failed after {state.get('replan_rounds', 0)} re-plan round(s) ({detail}). How should the run continue?",
                    "options": ["abandon_subtree", "abort_run"],
                    "default_on_timeout": None,
                    "evidence_refs": [result["report_ref"]],
                }
            )
        )
    _set_status(store, state["run_id"], "AWAITING_DECISION", "state_changed", {"reason": detail})
    return {"status": "AWAITING_DECISION", "note": detail}


def _decision_log(store: StateStore, run_id: str) -> list[str]:
    lines = []
    for row in store.conn.execute("SELECT payload FROM decisions WHERE run_id = ? AND status = 'RESOLVED' ORDER BY rowid", (run_id,)):
        data = json.loads(row["payload"])
        lines.append(f"- {data['request']['kind']}: {data['request']['question']} -> {data['resolution']['choice']}")
    return lines


def _node_report(state: RunState) -> dict[str, Any]:
    """Deliver the report (never deploy): requirements, acceptance evidence and the decision log, stored as one blob."""
    store: StateStore = _dep("state_store")
    blobs: BlobStore = _dep("blobs") or BlobStore()
    request = StructuredRequest.model_validate(state["request"])
    acceptance = state["acceptance"]
    text = "\n".join(
        [
            f"# Run {state['run_id']}",
            f"Request {request.request_id} ({request.task_type.value}), project {request.project_id}",
            "",
            "## Requirements",
            *[f"- {r.req_id}: {r.text}" for r in request.requirements],
            "",
            f"## Acceptance: {'passed' if acceptance['passed'] else 'failed'}",
            f"Report: {acceptance['report_ref']}",
            "",
            "## Decision log",
            *(_decision_log(store, state["run_id"]) or ["- (no decisions were needed)"]),
            "",
            "Nothing was deployed; review the changes before using them.",
        ]
    )
    ref = blobs.put(text.encode("utf-8"))
    _set_status(store, state["run_id"], "DONE", "run_completed", {"report_ref": ref})
    memory = _dep("memory")
    if memory is not None:
        memory.after_run(state["run_id"], "DONE")
    return {"status": "DONE", "report_ref": ref}


def build_run_graph(checkpointer: Any) -> Any:
    """create_run -> plan -> decompose -> monitor (until RootIntegrated) -> acceptance -> report, with bounded re-planning."""
    builder = StateGraph(RunState)
    builder.add_node("create_run", _node_create_run)
    builder.add_node("plan", _node_plan)
    builder.add_node("decompose", _node_decompose)
    builder.add_node("monitor", _node_monitor)
    builder.add_node("acceptance", _node_acceptance)
    builder.add_node("replan", _node_replan)
    builder.add_node("ask_user", _node_ask_user)
    builder.add_node("report", _node_report)

    builder.add_edge(START, "create_run")
    builder.add_edge("create_run", "plan")
    builder.add_conditional_edges("plan", _after_plan, {"decompose": "decompose", "end": END})
    builder.add_edge("decompose", "monitor")
    builder.add_conditional_edges("monitor", _after_monitor, {"acceptance": "acceptance", "end": END})
    builder.add_conditional_edges("acceptance", _after_acceptance, {"report": "report", "replan": "replan", "ask_user": "ask_user"})
    builder.add_edge("replan", "plan")
    builder.add_edge("ask_user", END)
    builder.add_edge("report", END)
    return builder.compile(checkpointer=checkpointer) if checkpointer is not None else builder.compile()


# -- composition root -------------------------------------------------------------------------------------------------


def _checkpointer(project_root: Path) -> Any:
    import sqlite3

    from langgraph.checkpoint.sqlite import SqliteSaver

    path = get_paths().checkpoints_db(project_root)
    return SqliteSaver(sqlite3.connect(str(path), check_same_thread=False))


def default_components(project_root: Path, run_id: str, overrides: dict[str, Any]) -> dict[str, Any]:
    """Build the real collaborators for a run; anything in ``overrides`` replaces the default of the same name.

    The model gateway, local runtime, workspace and tool executor are only built when the project is a git repository, so
    a plain directory can still be planned, paused and inspected.
    """
    components: dict[str, Any] = {}
    store = overrides.get("state_store") or StateStore.open(get_paths().state_db(project_root))
    broker = overrides.get("decision_broker") or DecisionBroker(store)
    components.update(state_store=store, decision_broker=broker, blobs=overrides.get("blobs") or BlobStore(), leaf_ids=set())
    components.setdefault("registry", ContractRegistry(store, broker))  # never created before: planned interfaces were not stored, so no worker saw a signature
    profile = overrides.get("profile") or ModelProfile.model_validate(
        {"model_id": "local", "backend": "llama-server", "c_eff_tokens": 8192, "max_slots": 1, "tokens_per_s": 20.0}
    )
    components["profile"] = profile
    components["frontier"] = overrides["frontier"] if overrides.get("frontier") is not None else Frontier(run_id, store)
    components["project_root"] = str(project_root)
    supervisor = RunSupervisor(run_id, store=store, scheduler=overrides.get("scheduler"), runtime=overrides.get("runtime"))

    def control() -> str | None:
        supervisor.poll_once()
        return {"PAUSED": "pause", "CANCELLED": "abort"}.get(supervisor.status)

    components["control"] = overrides.get("control") or control
    components["relay"] = overrides.get("relay") or OutboxRelay(store, EventLog(store.conn, components["blobs"]))
    components["supervisor"] = supervisor
    for name in ("gateway", "registry", "scheduler", "runtime", "driver", "regression", "acceptance", "authoring", "budget", "sleep", "max_ticks", "base_commit", "parent_branch", "lazy", "planner_strategy", "allow_local_tests", "profile_name"):
        if name in overrides:
            components[name] = overrides[name]
    if "scheduler" not in components and (project_root / ".git").exists():
        _build_execution(components, project_root, run_id, overrides)
    if "driver" not in components and "scheduler" in components:
        components["driver"] = _scheduler_driver(components)
    return components


def _build_execution(components: dict[str, Any], project_root: Path, run_id: str, overrides: dict[str, Any]) -> None:
    """The composition root for execution: runtime, workspace, tools, scheduler and the attempt runner (worker + gate)."""
    from asf.m4_execution.scheduler import TaskScheduler
    from asf.m4_execution.verification.gate import verify_change_set
    from asf.m4_execution.worker.worker_graph import run_attempt
    from asf.m5_shared.gateway.gateway import ModelGateway
    from asf.m5_shared.runtime.local_runtime import LocalRuntime
    from asf.m5_shared.tools.builtin_tools import register_builtin_tools
    from asf.m5_shared.tools.executor import ToolExecutor
    from asf.m5_shared.tools.registry import ToolRegistry
    from asf.m5_shared.workspace.workspace import Workspace

    store: StateStore = components["state_store"]
    workspace = overrides.get("workspace") or Workspace(project_root)
    runtime = overrides.get("runtime") or LocalRuntime(max_slots=1)
    run_budget = components.get("budget") or _default_budget(run_id)
    components["budget"] = run_budget
    gateway = components.get("gateway") or ModelGateway(str(overrides.get("profile_name") or ModelGateway.default_profile_name()), run_budget)
    gateway.budget = run_budget  # one budget per run: the CLI built its gateway with a placeholder, and nothing was ever counted against the limits
    gateway.metrics_db = project_root / ".factory" / "state.db"
    for role, name in dict(overrides.get("model_overrides") or {}).items():  # --model ROLE=NAME
        gateway.roles.setdefault(role, {})["model"] = name
    if overrides.get("strategy_overrides"):  # --strategy ROLE=NAME
        gateway.strategies.update(dict(overrides["strategy_overrides"]))
    tools = ToolRegistry()
    register_builtin_tools(tools)
    executor = ToolExecutor(registry=tools, broker=components["decision_broker"])
    outcomes: list[Any] = components.setdefault("outcomes", [])
    scheduler_box: dict[str, TaskScheduler] = {}

    def git(*args: str) -> str:
        code, out, _ = workspace._run_git(list(args))
        return out if code == 0 else ""

    def head() -> str:
        return git("rev-parse", "HEAD") or "HEAD"

    def commit_tests(paths: list[str], task_id: str) -> None:
        """The leaf's worktree is created from the base commit, so the acceptance tests must be in it."""
        workspace._run_git(["add", "--", *paths])
        workspace._run_git(["-c", "user.name=ASF", "-c", "user.email=asf@factory.local", "commit", "-m", f"acceptance tests for {task_id}", "--", *paths])

    def authoring(node: Any) -> list[str]:
        from asf.m3_orchestration.planning.test_authoring import author_acceptance_tests

        registry = components.get("registry")
        context = ""
        if registry is not None and node.contract_refs:
            modules = [ref.partition("@")[0] for ref in node.contract_refs]
            pinned = {ref.partition("@")[0]: ref.partition("@")[2] for ref in node.contract_refs if "@" in ref}
            capsules = registry.query(ContractQuery(module_ids=modules, pinned_versions=pinned))
            context = "PINNED CONTRACTS (the exact names and signatures the tests must use):\n" + "\n".join(f"- {c.module_id}.{c.operation}: " + " ".join(c.lines) for c in capsules)
        paths = author_acceptance_tests(
            node, bool(overrides.get("allow_local_tests")), gateway=gateway, project_root=project_root, broker=components["decision_broker"], context=context
        )
        commit_tests([*paths, *(["conftest.py"] if (project_root / "conftest.py").is_file() else [])], str(node.id))
        return paths

    components.setdefault("authoring", authoring)
    components.setdefault("base_commit", head)
    components.setdefault("parent_branch", git("rev-parse", "--abbrev-ref", "HEAD") or "main")
    gate_runner = overrides.get("gate_runner")
    if overrides.get("test_runner") is not None:
        components["test_runner"] = overrides["test_runner"]

    memory = overrides.get("memory") or components.get("memory")
    if memory is None and not overrides.get("no_memory"):
        try:
            from asf.m5_shared.memory.hooks import MemoryHooks

            memory = MemoryHooks.open(project_root, gateway=gateway)
        except Exception:  # noqa: BLE001 - memory is an aid, never a requirement: the run continues without it
            logger.warning("project memory is unavailable; running without it", exc_info=True)
    components["memory"] = memory

    def attempt(spec: Any, lease: Any, attempt_no: int) -> Any:
        # Runs on a scheduler thread: nothing here may touch the SQLite state store (its connection is thread-bound),
        # so contracts are promoted by the driver on the main thread rather than inside the gate. Memory has its own
        # thread-safe database.
        routed = memory.context_for(spec, run_id or None) if memory is not None else None
        change = run_attempt(
            spec, lease, attempt_no, workspace=workspace, gateway=gateway, executor=executor, runtime=runtime,
            failure_evidence=scheduler_box["s"].latest_evidence(str(spec.task_id)), memory_items=routed.items if routed is not None else None,
        )
        verdict = verify_change_set(
            change, workspace=workspace, gateway=gateway, allowed_files=list(spec.allowed_files), acceptance_refs=list(spec.acceptance_test_refs),
            runner=gate_runner,
        )
        if memory is not None and routed is not None:
            memory.after_attempt(spec, run_id or None, attempt_no, routed, verdict)
        return verdict

    scheduler = TaskScheduler(runtime=runtime, store=store, attempt_runner=attempt, outcome_sink=outcomes.append, spec_dir=project_root / ".factory" / "specs")
    scheduler_box["s"] = scheduler
    components.update(scheduler=scheduler, runtime=runtime, workspace=workspace, gateway=gateway, executor=executor)
    components["integrate"] = _make_integrate(components)


def _make_integrate(c: dict[str, Any]) -> Callable[[StateStore], None]:
    def integrate(store: StateStore) -> None:
        from asf.m4_execution.integration.integrator import integrate_parent
        from asf.m4_execution.verification.gate import run_in_sandbox

        parents = [str(r["task_id"]) for r in store.conn.execute("SELECT task_id FROM tasks WHERE state = 'DECOMPOSED' ORDER BY rowid DESC")]
        for parent_id in parents:  # deepest first: children are created after their parents
            integrate_parent(
                parent_id, state_store=store, workspace=c["workspace"], test_runner=c.get("test_runner") or run_in_sandbox, registry=c.get("registry"),
                scheduler=c["scheduler"], outcome_sink=c["outcomes"].append,
            )

    return integrate


def _scheduler_driver(c: dict[str, Any]) -> Driver:
    """One driver tick on the caller's thread: dispatch, record verified leaves, wake dependents, integrate finished parents."""
    store: StateStore = c["state_store"]
    scheduler = c["scheduler"]
    frontier: Frontier = c["frontier"]
    outcomes: list[Any] = c.setdefault("outcomes", [])
    counts = {"replans": 0, "resplits": 0}

    def tick() -> dict[str, Any] | None:
        result: dict[str, Any] = {"resplit": {}, "woken": 0}
        scheduler.dispatch_ready()
        for task_id in sorted(c["leaf_ids"]):
            if scheduler.state_of(task_id) == "VERIFIED" and not frontier.is_verified(task_id):
                row = store.conn.execute("SELECT version FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
                if row is not None:
                    store.commit(StateCommit.model_validate({"entity": "task", "entity_id": task_id, "expected_version": int(row["version"]), "mutation": {"state": "VERIFIED"}}))
                result["woken"] += frontier.wake_dependents(task_id)
                scheduler.mark_verified(task_id)
        while outcomes:
            outcome = outcomes.pop(0)
            row = store.conn.execute("SELECT version FROM tasks WHERE task_id = ?", (str(outcome.task_id),)).fetchone()
            if row is not None:  # the scheduler's ESCALATED is recorded on the task row, so a re-split can leave that state
                store.commit(
                    StateCommit.model_validate(
                        {"entity": "task", "entity_id": str(outcome.task_id), "expected_version": int(row["version"]), "mutation": {"state": "ESCALATED"}}
                    )
                )
            action = handle_escalation(outcome, store=store, broker=c["decision_broker"], replans_done=counts["replans"], resplits_done=counts["resplits"])
            if action in ("resplit", "replan"):
                counts["resplits" if action == "resplit" else "replans"] += 1
                result["resplit"][str(outcome.task_id)] = str(outcome.evidence_ref or "")
        integrator = c.get("integrate")
        if integrator is not None:
            integrator(store)
        return result if (result["resplit"] or result["woken"]) else None

    return tick


def start_run(request: StructuredRequest, project_root: Path, overrides: dict[str, Any]) -> str:
    """Create the run (budgets, mode) and drive the run graph in the foreground supervisor; return run_id.

    ``overrides`` may carry ready-made collaborators (state_store, gateway, scheduler, driver, ...) and ``run_id``,
    ``checkpointer``. A run that stops at a human decision returns its run_id; answer in the inbox and resume it.
    """
    run_id = str(overrides.get("run_id") or new_id("run"))
    start_trace(project_root, run_id)
    trace_event("run", "start", run=run_id, request=request.request_id, project=str(project_root), overrides=sorted(overrides))
    components = default_components(project_root, run_id, overrides)
    graph = build_run_graph(overrides.get("checkpointer") or _checkpointer(project_root))
    config: Any = {"configurable": {"thread_id": run_id, **components}}
    graph.invoke(
        {"request": request.model_dump(mode="json"), "run_id": run_id, "project_root": str(project_root)},
        config,
        **({"durability": "sync"} if overrides.get("checkpointer") is None else {}),
    )
    return run_id


def _set_status_outside_graph(store: StateStore, run_id: str, status: str) -> None:
    row = store.conn.execute("SELECT version FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    store.commit(
        StateCommit.model_validate(
            {
                "entity": "run", "entity_id": run_id, "expected_version": int(row["version"]) if row else None,
                "mutation": {"status": status}, "events": [_event(run_id, "state_changed", {"status": status})],
            }
        )
    )


def _resolved_choice(store: StateStore, decision_id: str) -> str | None:
    row = store.conn.execute("SELECT payload, status FROM decisions WHERE decision_id = ?", (decision_id,)).fetchone()
    if row is None or row["status"] != "RESOLVED":
        return None
    return str(json.loads(row["payload"])["resolution"]["choice"])


def resume_run(run_id: str, project_root: Path, overrides: dict[str, Any] | None = None) -> None:
    """Reconcile (state_store.recovery) then resume the graph by thread_id.

    Every pending interrupt whose decision has been answered is resumed with the user's choice; when none is answered
    yet, nothing happens (the run keeps waiting).
    """
    overrides = dict(overrides or {})
    start_trace(project_root, run_id)
    trace_event("run", "resume", run=run_id, project=str(project_root))
    components = default_components(project_root, run_id, overrides)
    store: StateStore = components["state_store"]
    if _restore_specs(project_root, store, components.get("scheduler")):
        logger.info("re-queued the leaves a previous process had certified")
    reconcile = overrides.get("reconcile")
    if reconcile is not None:
        reconcile(store)  # recovery.reconcile_on_startup, wired by the caller that owns the workspace and runtime
    graph = build_run_graph(overrides.get("checkpointer") or _checkpointer(project_root))
    config: Any = {"configurable": {"thread_id": run_id, **components}}
    snapshot = graph.get_state(config)
    resume: dict[str, str] = {}
    for task in snapshot.tasks:
        for pending in task.interrupts:
            if isinstance(pending.value, dict) and pending.value.get("paused"):
                row = store.conn.execute("SELECT status FROM runs WHERE run_id = ?", (run_id,)).fetchone()
                if row is not None and row["status"] == "PAUSED":
                    _set_status_outside_graph(store, run_id, "RUNNING")
                    resume[pending.id] = "resume"
                continue
            decision_id = str(pending.value.get("decision_id", "")) if isinstance(pending.value, dict) else ""
            choice = _resolved_choice(store, decision_id)
            if choice is not None:
                resume[pending.id] = choice
    if not snapshot.next:
        logger.info("run %s has nothing to resume", run_id)
        return
    if snapshot.tasks and not resume and any(t.interrupts for t in snapshot.tasks):
        logger.info("run %s is still waiting for a decision", run_id)
        return
    graph.invoke(Command(resume=resume) if resume else None, config)
