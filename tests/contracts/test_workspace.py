# FILE: tests/contracts/test_workspace.py
# ROLE: Tests that prove src/asf/contracts/workspace.py meets its DONE WHEN conditions.
# ARCH REF: p09 Artifact & Workspace Store; IF-15; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/workspace.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/workspace.py: WorkspaceOpKind, WorkspaceOp, WorkspaceResult (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_workspace.py` on Windows and Linux once src/asf/contracts/workspace.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_workspace.py` and `uv run mypy tests/contracts/test_workspace.py` are clean.



import pytest
from pydantic import ValidationError

from asf.contracts.workspace import WorkspaceOp, WorkspaceOpKind, WorkspaceResult


def test_operation_kinds() -> None:
    assert {k.value for k in WorkspaceOpKind} == {"create_worktree", "diff", "merge", "revert", "tag", "reset_to_base"}


def test_operation_only_requires_a_kind() -> None:
    op = WorkspaceOp.model_validate({"kind": "diff"})
    assert op.task_id is None and op.branch is None and op.base_commit is None
    with pytest.raises(ValidationError):
        WorkspaceOp.model_validate({})


def test_operation_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        WorkspaceOp.model_validate({"kind": "rebase"})


def test_operation_round_trip() -> None:
    op = WorkspaceOp.model_validate({"kind": "create_worktree", "task_id": "t1", "branch": "task/t1", "base_commit": "abc"})
    assert WorkspaceOp.model_validate_json(op.model_dump_json()) == op


def test_result_defaults_everything_but_the_verdict() -> None:
    res = WorkspaceResult.model_validate({"ok": True})
    assert res.commit is None and res.diff_ref is None and res.worktree_path is None and res.error_kind is None
    with pytest.raises(ValidationError):
        WorkspaceResult.model_validate({})


def test_failed_result_carries_an_error_kind() -> None:
    res = WorkspaceResult.model_validate({"ok": False, "error_kind": "merge_conflict"})
    assert res.ok is False and res.error_kind == "merge_conflict"
