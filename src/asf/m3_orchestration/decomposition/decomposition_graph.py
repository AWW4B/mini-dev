# FILE: src/asf/m3_orchestration/decomposition/decomposition_graph.py
# ROLE: Recursive Decomposition Engine graph: batched loop over the frontier, sizing, splitting, certification and dispatch.
# ARCH REF: M3; p05; IF-07a; IF-09; IF-10; IF-10b; D-06
# OWNS: Decomposition loop and report
# DOES NOT OWN: Executing leaves (M4)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/outcomes.py: ApprovedPlan, DecompositionReport, TaskOutcome (IF-07a/IF-10b/IF-10)
#   - imports from src/asf/m3_orchestration/decomposition/frontier.py: Frontier (frontier)
#   - imports from src/asf/m3_orchestration/decomposition/sizer.py: estimate_size, fits_leaf (sizing)
#   - imports from src/asf/m3_orchestration/decomposition/rubric.py: score_node (rubric)
#   - imports from src/asf/m3_orchestration/decomposition/splitter.py: propose_split (split)
#   - imports from src/asf/m3_orchestration/decomposition/split_validator.py: validate_split (validation)
#   - imports from src/asf/m3_orchestration/decomposition/leaf_certifier.py: certify_leaf (leaf)
#   - imports from src/asf/m3_orchestration/lifecycle.py: transition (state machine)
#   - imports from src/asf/m4_execution/scheduler.py: TaskScheduler (IF-09 enqueue)
#   - imports from src/asf/contracts/decisions.py: DecisionRequest (clarify / manual split requests)
#   - imports from src/asf/contracts/errors.py: AsfError (node processing errors)
#   - imports from src/asf/contracts/models.py: ModelProfile (the calibrated profile)
#   - imports from src/asf/contracts/tasks.py: TaskNode, TaskState (nodes)
#   - called by src/asf/m3_orchestration/run_graph.py: build_decomposition_graph
#   - called by tests/m3_orchestration/decomposition/test_decomposition_graph.py: build_decomposition_graph
#   - emits/consumes: emits node sizing/split events and emits narrative events TASK_RECEIVED, STEP_STARTED, HANDOFF_SENT, HANDOFF_RECEIVED (with causation_id set to the triggering event) via StateStore.commit
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Build the graph with LangGraph StateGraph; side-effecting steps use the Functional API @task so they are not re-run on resume (D-04).
#   6. Nodes must be idempotent up to any interrupt(): write the DecisionRequest through DecisionBroker first, then call interrupt() (D-06).
#   7. Pass thread_id = the run or node id; use the SqliteSaver from checkpoints.db with durability="sync" (D-05).
#   8. Loop in batches over the persisted frontier; check pause/budget flags each iteration.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/decomposition/test_decomposition_graph.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/decomposition/decomposition_graph.py` and `uv run mypy src/asf/m3_orchestration/decomposition/decomposition_graph.py` are clean.

import logging
from pathlib import Path
from typing import Any, TypedDict

from langgraph.config import get_config
from langgraph.graph import END, START, StateGraph

from asf.contracts.decisions import DecisionRequest
from asf.contracts.errors import AsfError
from asf.contracts.models import ModelProfile
from asf.contracts.outcomes import ApprovedPlan, DecompositionReport
from asf.contracts.tasks import TaskNode, TaskState
from asf.m3_orchestration.decomposition.frontier import Frontier
from asf.m3_orchestration.decomposition.leaf_certifier import certify_leaf
from asf.m3_orchestration.decomposition.rubric import score_node
from asf.m3_orchestration.decomposition.sizer import estimate_size, fits_leaf
from asf.m3_orchestration.decomposition.split_validator import validate_split
from asf.m3_orchestration.decomposition.splitter import propose_split
from asf.m3_orchestration.lifecycle import MAX_SPLIT_ATTEMPTS, transition
from asf.m4_execution.scheduler import TaskScheduler

logger = logging.getLogger(__name__)

BATCH_SIZE = 4
AMBIGUITY_LIMIT = 0.85  # above this the node is sent back for clarification instead of being sized
MAX_NODES = 500


class DecompositionState(TypedDict, total=False):
    plan: dict[str, Any]
    requirement_ids: list[str]
    resplit: dict[str, str]
    seeded: bool
    leaves: list[str]
    suspended: list[str]
    stop: str
    iterations: int
    nodes_created: int
    report: dict[str, Any]


def _dep(name: str, default: Any = None) -> Any:
    value = get_config().get("configurable", {}).get(name)
    return default if value is None else value


class _Engine:
    """One decomposition run's collaborators, read once from ``config["configurable"]``."""

    def __init__(self) -> None:
        self.frontier: Frontier = _dep("frontier")
        if self.frontier is None:
            raise RuntimeError("the decomposition graph needs 'frontier' in config['configurable']")
        self.gateway = _dep("gateway")
        profile: ModelProfile | None = _dep("profile")
        if profile is None:
            raise RuntimeError("the decomposition graph needs 'profile' (the calibrated ModelProfile) in config['configurable']")
        self.profile: ModelProfile = profile
        self.scheduler: TaskScheduler | None = _dep("scheduler")
        self.registry = _dep("registry")
        self.broker = _dep("decision_broker")
        self.authoring = _dep("authoring")
        self.control = _dep("control")  # callable -> None | "pause" | "abort", checked every iteration
        self.base_commit: Any = _dep("base_commit", "HEAD")  # a sha, or a callable returning the current one
        self.parent_branch: str = _dep("parent_branch", "main")
        self.project_root: Path | None = Path(_dep("project_root")) if _dep("project_root") else None
        self.lazy: bool = bool(_dep("lazy", False))
        self.batch: int = int(_dep("batch_size", BATCH_SIZE))
        self.max_nodes: int = int(_dep("max_nodes", MAX_NODES))
        self.rubric_gateway = _dep("rubric_gateway", self.gateway)
        self.skills = _dep("skills")

    def context_tokens(self, node: TaskNode) -> int:
        """Rough est_in for the files the node owns (4 characters per token), without reading anything large."""
        if self.project_root is None:
            return 0
        total = 0
        for rel in node.allowed_files:
            path = self.project_root / rel
            if path.is_file():
                total += min(path.stat().st_size, 200_000) // 4
        return total

    def ask(self, node: TaskNode, kind: str, question: str, options: list[str]) -> None:
        if self.broker is None:
            logger.warning("node %s needs a decision (%s) but no DecisionBroker is attached", node.id, kind)
            return
        self.broker.request(
            DecisionRequest.model_validate(
                {
                    "decision_id": f"dec-{kind}-{node.id}",
                    "run_id": str(node.run_id),
                    "task_id": str(node.id),
                    "kind": kind,
                    "requester": "asf.m3_orchestration.decomposition.decomposition_graph",
                    "question": question,
                    "options": options,
                    "default_on_timeout": None,  # no answer: the subtree stays suspended
                }
            )
        )


def _step(engine: _Engine, node: TaskNode, resplit_evidence: str | None) -> tuple[list[str], list[str], int]:
    """Size one node and either certify it as a leaf, split it, or park it. Returns (leaves, suspended, children_created)."""
    frontier = engine.frontier
    leaves: list[str] = []
    suspended: list[str] = []
    created = 0

    if resplit_evidence is None:
        if engine.lazy and any(not frontier.is_verified(str(d)) for d in node.deps):
            frontier.park(str(node.id))  # lazy expansion: wait until the interfaces it uses are implemented
            return leaves, [str(node.id)], created
        node = transition(node, TaskState.SIZING, "popped")

        size = estimate_size(node, engine.context_tokens(node))
        node = node.model_copy(update={"size_estimate": size})
        score = score_node(node, gateway=engine.rubric_gateway)
        if score.ambiguity > AMBIGUITY_LIMIT:
            node = transition(node, TaskState.AWAITING_INPUT, "ambiguous or contradictory")
            engine.ask(node, "clarify", f"Task '{node.goal}' is too ambiguous to size ({score.notes}). What exactly is meant?", ["clarified", "abandon_subtree"])
            frontier.update(node)
            return leaves, [str(node.id)], created
        if fits_leaf(node, size, engine.profile, risk=max(score.ambiguity, score.coupling)):
            spec = certify_leaf(
                node, engine.base_commit, engine.parent_branch, registry=engine.registry, authoring=engine.authoring
            )
            node = transition(node, TaskState.LEAF_CERTIFIED, "fits the leaf profile").model_copy(update={"kind": "leaf"})
            frontier.update(node)
            if engine.scheduler is not None:
                engine.scheduler.enqueue(spec)
            return [str(node.id)], suspended, created
        node = transition(node, TaskState.SPLITTING, "too big")
        feedback = ""
    else:
        node = transition(node, TaskState.SPLITTING, "re-split after an execution failure")
        feedback = f"The previous attempt at this task failed because it was too large. Evidence:\n{resplit_evidence}"

    # split: propose -> validate -> retry with the problems, bounded by the node's split attempts
    while True:
        sized: list[TaskNode] = []
        try:
            proposal = propose_split(node, gateway=engine.gateway, skills=engine.skills, feedback=feedback, role="T3" if node.counters.split_attempts < MAX_SPLIT_ATTEMPTS else "reviewer")
        except AsfError as err:  # the planner kept answering badly, is unreachable or out of budget: that attempt is lost, the node is not
            logger.warning("split proposal for %s failed: %s", node.id, err)
            problems = [f"the planner could not produce a split: {err}"]
        else:
            sized = [c.model_copy(update={"size_estimate": estimate_size(c, engine.context_tokens(c))}) for c in proposal.children]
            proposal = proposal.model_copy(update={"children": sized})
            problems = validate_split(node, proposal)
        if not problems:
            node = transition(node, TaskState.DECOMPOSED, "split committed")
            frontier.update(node)
            frontier.push(sized)
            return leaves, suspended, len(sized)
        feedback = "\n".join(f"- {p}" for p in problems)
        if node.counters.split_attempts >= MAX_SPLIT_ATTEMPTS:
            node = transition(node, TaskState.ESCALATED, "split budget exhausted")
            engine.ask(node, "manual_split", f"No valid split was found for '{node.goal}'. Problems: {'; '.join(problems)}", ["accept_larger_leaf", "abandon_subtree"])
            frontier.update(node)
            return leaves, [str(node.id)], created
        node = transition(node, TaskState.SPLITTING, "feed the validator errors back")


def _node_seed(state: DecompositionState) -> dict[str, Any]:
    engine = _Engine()
    if state.get("seeded"):
        return {}
    plan = ApprovedPlan.model_validate(state["plan"])
    nodes = [*plan.shared_type_nodes, *plan.module_nodes]  # shared types first: they are early leaves (A-2)
    engine.frontier.push([n.model_copy(update={"state": TaskState.PROPOSED}) for n in nodes])
    return {"seeded": True, "nodes_created": len(nodes), "leaves": [], "suspended": [], "iterations": 0, "stop": ""}


def _node_iterate(state: DecompositionState) -> dict[str, Any]:
    engine = _Engine()
    leaves = list(state.get("leaves", []))
    suspended = [s for s in state.get("suspended", [])]
    created_total = state.get("nodes_created", 0)

    command = engine.control() if callable(engine.control) else None
    if command in ("pause", "abort"):
        return {"stop": str(command)}
    if created_total >= engine.max_nodes:
        return {"stop": "budget"}

    work: list[tuple[TaskNode, str | None]] = []
    for node_id, evidence in state.get("resplit", {}).items():  # nodes that failed for size reasons come back first
        failed = engine.frontier.get(node_id)
        if failed is None:
            logger.warning("re-split requested for unknown node %s", node_id)
        else:
            work.append((failed, evidence or "(no evidence)"))
    work += [(n, None) for n in engine.frontier.pop_batch(engine.batch)]
    for node, resplit_evidence in work:
        try:
            new_leaves, new_suspended, created = _step(engine, node, resplit_evidence)
        except AsfError:
            logger.exception("node %s could not be processed", node.id)
            raise
        leaves += new_leaves
        suspended += new_suspended
        created_total += created
    return {"leaves": leaves, "suspended": list(dict.fromkeys(suspended)), "nodes_created": created_total, "iterations": state.get("iterations", 0) + 1, "stop": "", "resplit": {}}


def _after_iterate(state: DecompositionState) -> str:
    engine = _Engine()
    if state.get("stop") or len(engine.frontier) == 0:
        return "report"
    return "iterate"


def _node_report(state: DecompositionState) -> dict[str, Any]:
    engine = _Engine()
    suspended = list(dict.fromkeys([*state.get("suspended", []), *engine.frontier.deferred_ids()]))
    wanted = list(state.get("requirement_ids", []))
    plan = ApprovedPlan.model_validate(state["plan"]) if state.get("plan") else None
    texts = []
    if plan is not None:
        for n in [plan.root, *plan.module_nodes, *plan.shared_type_nodes]:
            texts.append(" ".join([n.goal, *n.acceptance_refs]))
    untraced = [r for r in wanted if not any(r in t for t in texts)]
    stopped = state.get("stop", "")
    report = DecompositionReport.model_validate(
        {
            "run_id": plan.run_id if plan is not None else "",
            "complete": not stopped and len(engine.frontier) == 0 and not suspended and not untraced,
            "untraced_requirements": untraced,
            "suspended_nodes": suspended,
        }
    )
    return {"report": report.model_dump(mode="json")}


def build_decomposition_graph(checkpointer: Any) -> Any:
    """Seed the frontier from the ApprovedPlan, then loop in batches: size, certify or split, until the frontier is empty or the run stops.

    Collaborators come from ``config["configurable"]``: frontier, profile (required); gateway, scheduler, registry,
    decision_broker, authoring, control, base_commit, parent_branch, project_root, lazy, batch_size, max_nodes.
    """
    builder = StateGraph(DecompositionState)
    builder.add_node("seed", _node_seed)
    builder.add_node("iterate", _node_iterate)
    builder.add_node("report", _node_report)
    builder.add_edge(START, "seed")
    builder.add_edge("seed", "iterate")
    builder.add_conditional_edges("iterate", _after_iterate, {"iterate": "iterate", "report": "report"})
    builder.add_edge("report", END)
    return builder.compile(checkpointer=checkpointer) if checkpointer is not None else builder.compile()
