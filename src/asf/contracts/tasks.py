# FILE: src/asf/contracts/tasks.py
# ROLE: Defines the task-node records, node states (p06) and the leaf task spec (IF-09).
# ARCH REF: p05; p06 states; p15 TaskNode, LeafTaskSpec, AttemptRecord; IF-09 ReadyTask; A-2, A-3
# OWNS: Task data shapes and the state enum
# DOES NOT OWN: State transitions (src/asf/m3_orchestration/lifecycle.py); persistence (state_store)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/ids.py: AttemptId, LeaseId, RunId, TaskId (typed ids)
#   - imports from src/asf/contracts/contract_spec.py: ContractCapsule (A-1 capsules pinned on leaves)
#   - called by src/asf/contracts/outcomes.py: TaskNode
#   - called by src/asf/m5_shared/state_store/store.py: TaskNode, TaskState
#   - called by src/asf/m3_orchestration/lifecycle.py: TaskNode, TaskState
#   - called by src/asf/m3_orchestration/planning/test_authoring.py: TaskNode
#   - called by src/asf/m3_orchestration/decomposition/frontier.py: TaskNode
#   - called by src/asf/m3_orchestration/decomposition/sizer.py: TaskNode
#   - called by src/asf/m3_orchestration/decomposition/rubric.py: TaskNode
#   - called by src/asf/m3_orchestration/decomposition/splitter.py: TaskNode
#   - called by src/asf/m3_orchestration/decomposition/split_validator.py: TaskNode
#   - called by src/asf/m3_orchestration/decomposition/leaf_certifier.py: TaskNode, LeafTaskSpec
#   - called by src/asf/m4_execution/scheduler.py: LeafTaskSpec
#   - called by src/asf/m4_execution/worker/strategies.py: LeafTaskSpec
#   - called by src/asf/m4_execution/worker/worker_graph.py: LeafTaskSpec
#   - called by src/asf/m4_execution/integration/repair.py: TaskNode
#   - called by src/asf/cli/views/task_tree_view.py: TaskNode
#   - called by tests/contracts/test_tasks.py: NodeKind, TaskState, NodeCounters, TaskNode, StepBudget, LeafTaskSpec, AttemptRecord
#   - called by src/asf/m4_execution/integration/integrator.py: LeafTaskSpec, TaskNode
#   - called by tests/m3_orchestration/test_lifecycle.py: TaskNode, TaskState
#   - called by src/asf/m3_orchestration/planning/planner_graph.py: TaskNode
#   - called by tests/m3_orchestration/planning/test_test_authoring.py: TaskNode
#   - called by src/asf/m3_orchestration/decomposition/decomposition_graph.py: TaskNode, TaskState
#   - called by tests/m3_orchestration/decomposition/test_sizer.py: TaskNode
#   - called by tests/m3_orchestration/decomposition/test_rubric.py: TaskNode
#   - called by tests/m3_orchestration/decomposition/test_splitter.py: TaskNode
#   - called by tests/m3_orchestration/decomposition/test_split_validator.py: TaskNode
#   - called by tests/m3_orchestration/decomposition/test_leaf_certifier.py: TaskNode
#   - called by tests/m3_orchestration/decomposition/test_frontier.py: TaskNode
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. This file is declarations only: Pydantic models, enums and type aliases. Add field validators only where the docstring of a field states a constraint.
#   6. Every model must round-trip through model_dump_json() / model_validate_json() unchanged; the JSON Schema exported from these models is the published contract (D-39: no hand-written JSON).
#   7. Changing a field name or type is a contract change: stop and report instead.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; business logic; I/O; imports from asf.m1-m5 packages, asf.cli, asf.web or asf.platform
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/contracts/test_tasks.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/contracts/tasks.py` and `uv run mypy src/asf/contracts/tasks.py` are clean.

from enum import StrEnum

from pydantic import BaseModel, Field

from asf.contracts.contract_spec import ContractCapsule
from asf.contracts.ids import AttemptId, LeaseId, RunId, TaskId


class NodeKind(StrEnum):
    COMPOSITE = "composite"
    LEAF = "leaf"
    INTEGRATION = "integration"
    REPAIR = "repair"
    SHARED_TYPES = "shared_types"  # A-2: shared types/utilities become early leaves


class TaskState(StrEnum):
    PROPOSED = "PROPOSED"
    DEFERRED = "DEFERRED"
    SIZING = "SIZING"
    AWAITING_INPUT = "AWAITING_INPUT"
    SPLITTING = "SPLITTING"
    DECOMPOSED = "DECOMPOSED"
    LEAF_CERTIFIED = "LEAF_CERTIFIED"
    BLOCKED = "BLOCKED"
    READY = "READY"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    FAILED_ATTEMPT = "FAILED_ATTEMPT"
    CHILDREN_DONE = "CHILDREN_DONE"
    INTEGRATING = "INTEGRATING"
    REPAIRING = "REPAIRING"
    INTEGRATED = "INTEGRATED"
    ESCALATED = "ESCALATED"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"
    ABANDONED = "ABANDONED"


class NodeCounters(BaseModel):
    split_attempts: int = 0
    resplits: int = 0
    attempts: int = 0
    interruptions: int = 0
    repair_rounds: int = 0


class TaskNode(BaseModel):
    id: TaskId
    run_id: RunId
    parent_id: TaskId | None = None
    kind: NodeKind
    goal: str
    acceptance_refs: list[str] = Field(default_factory=list)
    contract_refs: list[str] = Field(default_factory=list, description="module@version")
    deps: list[TaskId] = Field(default_factory=list)
    allowed_files: list[str] = Field(default_factory=list, description="POSIX-style relative paths inside the project workspace")
    priority: int = 0
    state: TaskState = TaskState.PROPOSED
    prior_state: TaskState | None = None
    size_estimate: int | None = Field(default=None, description="S(n) = est_in + est_out tokens (alpha-progress rule)")
    depth: int = 0
    counters: NodeCounters = Field(default_factory=NodeCounters)
    idempotency_key: str


class StepBudget(BaseModel):
    max_turns: int = 12
    max_output_tokens_per_turn: int = 2048
    wall_clock_s: int = 900


class LeafTaskSpec(BaseModel):
    """IF-09 ReadyTask payload."""
    task_id: TaskId
    goal: str
    acceptance_test_refs: list[str] = Field(description="written by the planner tier T3 only (A-4)")
    capsules: list[ContractCapsule] = Field(description="pinned dependency capsules, 3-5 lines each (A-1)")
    allowed_files: list[str]
    read_only_files: list[str] = Field(default_factory=list)
    context_budget_tokens: int
    model_role: str = "T2"
    step_budget: StepBudget = Field(default_factory=StepBudget)
    max_attempts: int = Field(default=3, description="A-3: bounded retries, then re-split or escalate")
    base_commit: str
    parent_branch: str


class AttemptRecord(BaseModel):
    attempt_id: AttemptId
    task_id: TaskId
    attempt_no: int
    lease_id: LeaseId | None = None
    model: str
    tier: str
    strategy: str
    context_pack_id: str | None = None
    diff_ref: str | None = None
    failure_class: str | None = None
    evidence_ref: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    inference_s: float = 0.0
    measured: bool = True
