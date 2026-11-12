# FILE: src/asf/contracts/outcomes.py
# ROLE: Defines failure classes, TaskOutcome (IF-10), ChangeSet/Requeue (IF-21), ApprovedPlan (IF-07a), DecompositionReport (IF-10b) and RootIntegrated (IF-10c).
# ARCH REF: p05; p07; p08; p16; IF-07a; IF-10; IF-10b; IF-10c; IF-21
# OWNS: Outcome shapes
# DOES NOT OWN: Classification logic (verification/failure_classifier.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/ids.py: RunId, TaskId (typed ids)
#   - imports from src/asf/contracts/tasks.py: TaskNode (plan nodes)
#   - called by src/asf/m3_orchestration/run_graph.py: DecompositionReport, RootIntegrated
#   - called by src/asf/m3_orchestration/escalation.py: TaskOutcome, FailureClass
#   - called by src/asf/m3_orchestration/planning/planner_graph.py: ApprovedPlan
#   - called by src/asf/m3_orchestration/decomposition/decomposition_graph.py: ApprovedPlan, DecompositionReport, TaskOutcome
#   - called by src/asf/m4_execution/scheduler.py: Requeue, TaskOutcome
#   - called by src/asf/m4_execution/worker/worker_graph.py: ChangeSet
#   - called by src/asf/m4_execution/verification/test_selection.py: ChangeSet
#   - called by src/asf/m4_execution/verification/failure_classifier.py: FailureClass
#   - called by src/asf/m4_execution/verification/reviewer.py: ChangeSet
#   - called by src/asf/m4_execution/verification/gate.py: ChangeSet, Requeue, TaskOutcome
#   - called by src/asf/m4_execution/integration/integrator.py: RootIntegrated
#   - called by tests/contracts/test_outcomes.py: FailureClass, TaskOutcome, ChangeSet, Requeue, ApprovedPlan, DecompositionReport, RootIntegrated
#   - called by tests/m4_execution/test_scheduler.py: Requeue, TaskOutcome
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
# DONE WHEN: (1) tests/contracts/test_outcomes.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/contracts/outcomes.py` and `uv run mypy src/asf/contracts/outcomes.py` are clean.

from enum import StrEnum

from pydantic import BaseModel, Field

from asf.contracts.ids import RunId, TaskId
from asf.contracts.tasks import TaskNode


class FailureClass(StrEnum):
    LOCAL_BUG = "LOCAL_BUG"
    FLAKY = "FLAKY"
    ENV_INFRA = "ENV_INFRA"
    CONTRACT_MISMATCH = "CONTRACT_MISMATCH"
    SPEC_TOO_LARGE = "SPEC_TOO_LARGE"
    CONTEXT_OVERFLOW = "CONTEXT_OVERFLOW"
    CONTRACT_GAP = "CONTRACT_GAP"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    ESCALATED = "ESCALATED"


class TaskOutcome(BaseModel):
    """IF-10."""
    task_id: TaskId
    failure_class: FailureClass
    evidence_ref: str | None = None
    attempts: int


class ChangeSet(BaseModel):
    """IF-21 worker -> gate."""
    task_id: TaskId
    attempt_no: int
    diff_ref: str
    worktree_path: str
    files_touched: list[str]
    self_report: str


class Requeue(BaseModel):
    """IF-21 gate -> scheduler."""
    task_id: TaskId
    failure_class: FailureClass
    evidence_ref: str


class ApprovedPlan(BaseModel):
    """IF-07a planner -> decomposition."""
    run_id: RunId
    root: TaskNode
    module_nodes: list[TaskNode]
    shared_type_nodes: list[TaskNode] = Field(default_factory=list, description="A-2 early leaves")
    contract_ids: list[str]


class DecompositionReport(BaseModel):
    """IF-10b."""
    run_id: RunId
    complete: bool
    untraced_requirements: list[str]
    suspended_nodes: list[TaskId]


class RootIntegrated(BaseModel):
    """IF-10c."""
    run_id: RunId
    root_task: TaskId
    report_ref: str
