# FILE: src/asf/m3_orchestration/planning/planner_graph.py
# ROLE: Planning Agent graph: plan the module tree, declare contracts top-down (A-1), add shared-type leaves (A-2), and get approval.
# ARCH REF: M3; p04 Planning Agent; IF-07; IF-07a ApprovedPlan; A-1; A-2
# OWNS: Plan production and approval
# DOES NOT OWN: Decomposing below module level
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/outcomes.py: ApprovedPlan (IF-07a)
#   - imports from src/asf/m3_orchestration/planning/modes.py: select_mode (mode)
#   - imports from src/asf/m3_orchestration/planning/strategies.py: run_planner_strategy (strategy)
#   - imports from src/asf/m5_shared/registry/registry.py: ContractRegistry (IF-07/IF-08)
#   - imports from src/asf/m5_shared/context/context_service.py: ContextService (IF-11 ContextPack)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (IF-03 decisions)
#   - imports from src/asf/contracts/contract_spec.py: ContractSpec (DRAFT contracts)
#   - imports from src/asf/contracts/decisions.py: DecisionRequest (APPROVE_PLAN request)
#   - imports from src/asf/contracts/errors.py: ApprovalRequired, ProviderUnavailable (approval needed / planner tier down)
#   - imports from src/asf/contracts/requests.py: StructuredRequest (the request being planned)
#   - imports from src/asf/contracts/tasks.py: TaskNode (root and module nodes)
#   - called by src/asf/m3_orchestration/run_graph.py: build_planner_graph, plan_result, PlanModel
#   - called by tests/m3_orchestration/planning/test_planner_graph.py: build_planner_graph, check_plan, plan_result, PlanModel
#   - emits/consumes: raises DecisionRequest kind APPROVE_PLAN; emits narrative events TASK_RECEIVED, STEP_STARTED, HANDOFF_SENT, HANDOFF_RECEIVED (with causation_id set to the triggering event) via StateStore.commit
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
# DONE WHEN: (1) tests/m3_orchestration/planning/test_planner_graph.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/planning/planner_graph.py` and `uv run mypy src/asf/m3_orchestration/planning/planner_graph.py` are clean.

import hashlib
import logging
from collections.abc import Mapping
from typing import Any, TypedDict, cast

from langgraph.config import get_config
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from asf.contracts.contract_spec import ContractSpec
from asf.contracts.decisions import DecisionRequest
from asf.contracts.errors import ApprovalRequired, ProviderUnavailable
from asf.contracts.outcomes import ApprovedPlan
from asf.contracts.requests import StructuredRequest
from asf.contracts.tasks import TaskNode
from asf.m3_orchestration.planning.modes import PlanMode, select_mode
from asf.m3_orchestration.planning.strategies import PlannerStrategyName, run_planner_strategy
from asf.m5_shared.registry.registry import ContractRegistry

logger = logging.getLogger(__name__)

MAX_REVISIONS = 2
CONTRACT_VERSION = "0.1.0"


class InterfaceSpec(BaseModel):
    name: str
    signature: str
    returns: str = "None"
    errors: list[str] = Field(default_factory=list)
    example: str = ""


class ModuleSpec(BaseModel):
    name: str
    goal: str
    files: list[str]
    interfaces: list[InterfaceSpec] = Field(default_factory=list)
    deps: list[str] = Field(default_factory=list)
    acceptance: list[str] = Field(default_factory=list)
    covers: list[str] = Field(default_factory=list, description="requirement ids this module is responsible for")


class PlanModel(BaseModel):
    modules: list[ModuleSpec]
    shared_types: list[ModuleSpec] = Field(default_factory=list, description="A-2: shared types and utilities become early leaves")
    assumptions: list[str] = Field(default_factory=list)
    open_decisions: list[str] = Field(default_factory=list)


class PlannerState(TypedDict, total=False):
    request: dict[str, Any]
    run_id: str
    mode: str
    plan: dict[str, Any]
    problems: list[str]
    revisions: int
    degraded: bool
    approved: bool
    approved_plan: dict[str, Any] | None
    note: str


_MODE_GUIDANCE = {
    PlanMode.DESIGN: "Design a module tree with interface contracts, acceptance criteria and a verification plan.",
    PlanMode.DIAGNOSIS: "Plan a bounded fix: first a reproduction test spec, then localisation hypotheses, then the smallest fix scope.",
    PlanMode.IMPACT: "Name the affected modules and contracts, whether the contract delta is breaking, and the regression scope. Characterisation tests come first.",
}


def _dependency(name: str) -> Any:
    try:
        return get_config().get("configurable", {}).get(name)
    except RuntimeError:
        return None


def _prompt(request: StructuredRequest, mode: PlanMode, problems: list[str]) -> str:
    reqs = "\n".join(f"- {r.req_id}: {r.text}" for r in request.requirements) or "(none)"
    text = (
        f"MODE: {mode.value}. {_MODE_GUIDANCE[mode]}\n"
        f"REQUIREMENTS:\n{reqs}\nCONSTRAINTS: {'; '.join(request.constraints) or '-'}\n"
        f"ACCEPTANCE: {'; '.join(request.acceptance) or '-'}\nASSUMPTIONS: {'; '.join(request.assumptions) or '-'}\n"
        "Every requirement must be covered by at least one module (list its id under 'covers'). Every dependency must name "
        "another module. List assumptions and open decisions; never resolve them silently."
    )
    if request.repo_profile is not None:
        text += f"\nEXISTING REPOSITORY: languages {request.repo_profile.languages}"
    if problems:
        text += "\nTHE PREVIOUS PLAN FAILED THESE CHECKS (fix only these):\n- " + "\n- ".join(problems)
    return text


def check_plan(plan: PlanModel, request: StructuredRequest) -> list[str]:
    """Plan checks: requirement coverage, a producer for every dependency, an acyclic module graph."""
    problems: list[str] = []
    modules = [*plan.shared_types, *plan.modules]
    names = [m.name for m in modules]
    if not plan.modules:
        problems.append("the plan has no modules")
    problems += [f"module name '{n}' is used twice" for n in dict.fromkeys(n for n in names if names.count(n) > 1)]
    covered = {c for m in modules for c in m.covers}
    for req in request.requirements:
        if req.req_id not in covered and not any(req.req_id in a for m in modules for a in m.acceptance):
            problems.append(f"requirement {req.req_id} is not covered by any module")
    for m in modules:
        if not m.files:
            problems.append(f"module '{m.name}' owns no files")
        for dep in m.deps:
            if dep not in names:
                problems.append(f"module '{m.name}' depends on '{dep}', which nobody produces")
    # cycle check (Kahn): whatever cannot be ordered is on a cycle
    remaining = {m.name: {d for d in m.deps if d in names} for m in modules}
    while True:
        free = [n for n, deps in remaining.items() if not deps]
        if not free:
            break
        for n in free:
            del remaining[n]
        for deps in remaining.values():
            deps.difference_update(free)
    if remaining:
        problems.append(f"the module dependencies contain a cycle among: {', '.join(sorted(remaining))}")
    return problems


def _node_mode(state: PlannerState) -> dict[str, Any]:
    return {"mode": select_mode(StructuredRequest.model_validate(state["request"])).value, "revisions": state.get("revisions", 0)}


def _node_plan(state: PlannerState) -> dict[str, Any]:
    gateway = _dependency("gateway")
    if gateway is None:
        raise RuntimeError("the planner graph needs 'gateway' in config['configurable']")
    request = StructuredRequest.model_validate(state["request"])
    prompt = _prompt(request, PlanMode(state["mode"]), state.get("problems", []))
    strategy = cast(PlannerStrategyName, _dependency("planner_strategy") or "self_critique")
    degraded = state.get("degraded", False)
    try:
        plan = run_planner_strategy(strategy, gateway, prompt, PlanModel, role="T2" if degraded else "T3")
    except ProviderUnavailable:
        if degraded:
            raise
        logger.warning("planning tier unreachable; degrading to the local planner with mandatory approval")
        plan = run_planner_strategy(strategy, gateway, prompt, PlanModel, role="T2")
        degraded = True
    return {"plan": plan.model_dump(), "degraded": degraded}


def _node_check(state: PlannerState) -> dict[str, Any]:
    problems = check_plan(PlanModel.model_validate(state["plan"]), StructuredRequest.model_validate(state["request"]))
    return {"problems": problems, "revisions": state.get("revisions", 0) + (1 if problems else 0)}


def _after_check(state: PlannerState) -> str:
    return "plan" if state.get("problems") and state.get("revisions", 0) <= MAX_REVISIONS else "approve"


def _approval_required(state: PlannerState) -> bool:
    """Always for a new build, a degraded plan or a plan that still fails its checks; never for plain small changes."""
    return state.get("mode") == PlanMode.DESIGN.value or bool(state.get("degraded")) or bool(state.get("problems"))


def _node_approve(state: PlannerState) -> dict[str, Any]:
    if not _approval_required(state):
        return {"approved": True}
    broker = _dependency("decision_broker")
    if broker is None:
        raise ApprovalRequired("The plan needs your approval but no DecisionBroker is attached to this run.")
    run_id = state["run_id"]
    plan = PlanModel.model_validate(state["plan"])
    summary = "; ".join(f"{m.name} ({len(m.files)} file(s))" for m in plan.modules)
    failed = f" Failed checks: {'; '.join(state.get('problems', []))}." if state.get("problems") else ""
    broker.request(
        DecisionRequest.model_validate(
            {
                "decision_id": f"dec-plan-{run_id}",
                "run_id": run_id,
                "kind": "approve_plan",
                "requester": "asf.m3_orchestration.planning.planner_graph",
                "question": f"Approve this {state['mode']} plan? Modules: {summary}.{' (degraded local planner)' if state.get('degraded') else ''}{failed}",
                "options": ["approve", "reject"],
                "default_on_timeout": None,
            }
        )
    )
    answer = interrupt({"decision_id": f"dec-plan-{run_id}", "options": ["approve", "reject"]})
    return {"approved": str(answer) == "approve"}


def _after_approve(state: PlannerState) -> str:
    return "emit" if state.get("approved") else "rejected"


def _node_rejected(state: PlannerState) -> dict[str, Any]:
    return {"approved_plan": None, "note": "plan rejected: the run is cancelled"}


def _task_node(run_id: str, name: str, kind: str, module: ModuleSpec | None, deps: list[str], goal: str, parent: str | None) -> TaskNode:
    key = hashlib.sha256(f"{run_id}|{name}|{goal}".encode()).hexdigest()[:24]
    return TaskNode.model_validate(
        {
            "id": f"{run_id}-{name}",
            "run_id": run_id,
            "parent_id": parent,
            "kind": kind,
            "goal": goal,
            "acceptance_refs": list(module.acceptance) if module else [],
            "contract_refs": [f"{name}@{CONTRACT_VERSION}"] if module and module.interfaces else [],
            "deps": deps,
            "allowed_files": list(module.files) if module else [],
            "depth": 0 if parent is None else 1,
            "idempotency_key": key,
        }
    )


def _node_emit(state: PlannerState) -> dict[str, Any]:
    run_id = state["run_id"]
    request = StructuredRequest.model_validate(state["request"])
    plan = PlanModel.model_validate(state["plan"])
    registry: ContractRegistry | None = _dependency("registry")

    contract_ids: list[str] = []
    for module in [*plan.shared_types, *plan.modules]:
        if not module.interfaces:
            continue
        spec = ContractSpec.model_validate(
            {
                "contract_id": f"c-{run_id}-{module.name}",
                "module_id": module.name,
                "version": CONTRACT_VERSION,
                "status": "DRAFT",
                "operations": [i.model_dump() for i in module.interfaces],
            }
        )
        if registry is not None:
            registry.register(spec)
        contract_ids.append(str(spec.contract_id))

    def node_id(name: str) -> str:
        return f"{run_id}-{name}"

    root = _task_node(run_id, "root", "composite", None, [], f"Deliver: {'; '.join(r.text for r in request.requirements)[:300]}", None)
    shared = [_task_node(run_id, m.name, "shared_types", m, [node_id(d) for d in m.deps], m.goal, root.id) for m in plan.shared_types]
    shared_ids = [str(s.id) for s in shared]
    modules = [
        _task_node(run_id, m.name, "composite", m, [*(node_id(d) for d in m.deps), *shared_ids], m.goal, root.id) for m in plan.modules
    ]
    approved = ApprovedPlan.model_validate(
        {"run_id": run_id, "root": root, "module_nodes": modules, "shared_type_nodes": shared, "contract_ids": contract_ids}
    )
    return {"approved_plan": approved.model_dump(mode="json"), "note": f"plan approved with {len(modules)} module(s)"}


def build_planner_graph(checkpointer: Any) -> Any:
    """Plan -> check (revise at most twice) -> approve (HITL) -> register contracts and emit the ApprovedPlan.

    Collaborators come from ``config["configurable"]``: gateway (required), decision_broker, registry, planner_strategy.
    """
    builder = StateGraph(PlannerState)
    builder.add_node("mode", _node_mode)
    builder.add_node("plan", _node_plan)
    builder.add_node("check", _node_check)
    builder.add_node("approve", _node_approve)
    builder.add_node("emit", _node_emit)
    builder.add_node("rejected", _node_rejected)

    builder.add_edge(START, "mode")
    builder.add_edge("mode", "plan")
    builder.add_edge("plan", "check")
    builder.add_conditional_edges("check", _after_check, {"plan": "plan", "approve": "approve"})
    builder.add_conditional_edges("approve", _after_approve, {"emit": "emit", "rejected": "rejected"})
    builder.add_edge("emit", END)
    builder.add_edge("rejected", END)
    return builder.compile(checkpointer=checkpointer) if checkpointer is not None else builder.compile()


def plan_result(output: Mapping[str, Any]) -> ApprovedPlan | None:
    """The ApprovedPlan from a finished planner graph run, or None when the plan was rejected."""
    raw = output.get("approved_plan")
    return ApprovedPlan.model_validate(raw) if raw else None
