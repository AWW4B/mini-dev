# FILE: src/asf/contracts/workspace.py
# ROLE: Defines WorkspaceOp and WorkspaceResult (IF-15).
# ARCH REF: p09 Artifact & Workspace Store; IF-15
# OWNS: Workspace operation shapes
# DOES NOT OWN: Executing VCS operations
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/ids.py: TaskId (typed ids)
#   - called by src/asf/m5_shared/workspace/workspace.py: WorkspaceOp, WorkspaceResult
#   - called by tests/contracts/test_workspace.py: WorkspaceOpKind, WorkspaceOp, WorkspaceResult
#   - called by src/asf/m5_shared/state_store/recovery.py: WorkspaceOp
#   - called by src/asf/m4_execution/verification/gate.py: WorkspaceOp
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
# DONE WHEN: (1) tests/contracts/test_workspace.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/contracts/workspace.py` and `uv run mypy src/asf/contracts/workspace.py` are clean.

from enum import StrEnum

from pydantic import BaseModel

from asf.contracts.ids import TaskId


class WorkspaceOpKind(StrEnum):
    CREATE_WORKTREE = "create_worktree"
    DIFF = "diff"
    MERGE = "merge"
    REVERT = "revert"
    TAG = "tag"
    RESET_TO_BASE = "reset_to_base"


class WorkspaceOp(BaseModel):
    """IF-15 request."""
    kind: WorkspaceOpKind
    task_id: TaskId | None = None
    branch: str | None = None
    base_commit: str | None = None


class WorkspaceResult(BaseModel):
    """IF-15 response."""
    ok: bool
    commit: str | None = None
    diff_ref: str | None = None
    worktree_path: str | None = None
    error_kind: str | None = None
