# FILE: src/asf/contracts/decisions.py
# ROLE: Defines DecisionRequest (IF-03) and DecisionResolved (IF-04).
# ARCH REF: p10 Decision Broker; p02 Decision Inbox; IF-03; IF-04; D-10; D-21; D-22
# OWNS: HITL request/answer shapes and kinds
# DOES NOT OWN: Persistence and routing (src/asf/m5_shared/decisions/broker.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/ids.py: DecisionId, RunId, TaskId (typed ids)
#   - called by src/asf/m5_shared/decisions/broker.py: DecisionRequest, DecisionResolved, NEVER_AUTO_APPROVED
#   - called by src/asf/cli/views/inbox_view.py: DecisionRequest
#   - called by tests/contracts/test_decisions.py: DecisionKind, DecisionRequest, DecisionResolved, NEVER_AUTO_APPROVED
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
# DONE WHEN: (1) tests/contracts/test_decisions.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/contracts/decisions.py` and `uv run mypy src/asf/contracts/decisions.py` are clean.

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from asf.contracts.ids import DecisionId, RunId, TaskId


class DecisionKind(StrEnum):
    CLARIFY = "clarify"
    APPROVE_PLAN = "approve_plan"
    BREAKING_CONTRACT = "breaking_contract"
    TOOL_PERMISSION = "tool_permission"
    BUDGET_RAISE = "budget_raise"
    ESCALATION = "escalation"
    MANUAL_SPLIT = "manual_split"
    UNSANDBOXED_EXECUTION = "unsandboxed_execution"
    DEPENDENCY_INSTALL = "dependency_install"
    NO_WHEEL_EXCEPTION = "no_wheel_exception"
    APPROVE_LOCAL_TESTS = "approve_local_tests"


NEVER_AUTO_APPROVED: frozenset[DecisionKind] = frozenset({
    DecisionKind.BREAKING_CONTRACT, DecisionKind.TOOL_PERMISSION, DecisionKind.BUDGET_RAISE,
    DecisionKind.UNSANDBOXED_EXECUTION, DecisionKind.DEPENDENCY_INSTALL, DecisionKind.NO_WHEEL_EXCEPTION,
})


class DecisionRequest(BaseModel):
    """IF-03."""
    decision_id: DecisionId
    run_id: RunId
    task_id: TaskId | None = None
    kind: DecisionKind
    requester: str = Field(description="module path of the requester, used for routing IF-04")
    question: str
    options: list[str]
    default_on_timeout: str | None = Field(description="must be safe; None means keep pending")
    deadline: datetime | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class DecisionResolved(BaseModel):
    """IF-04."""
    decision_id: DecisionId
    choice: str
    text: str | None = None
    answered_by: str
    answered_at: datetime
    applied_default: bool = False
