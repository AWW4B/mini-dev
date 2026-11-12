# FILE: src/asf/m5_shared/workspace/workspace.py
# ROLE: Runs git operations for the project workspace: per-attempt worktrees, diffs, merges, reverts, tags (IF-15).
# ARCH REF: M5; p09 Artifact & Workspace Store; IF-15 WorkspaceOps; D-04 @task side effects
# OWNS: git invocation and per-branch locks
# DOES NOT OWN: Deciding when to merge (verification gate)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/workspace.py: WorkspaceOp, WorkspaceResult (IF-15)
#   - imports from src/asf/platform/select.py: get_platform (platform adapter)
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (diff storage)
#   - called by src/asf/m5_shared/state_store/recovery.py: Workspace
#   - called by src/asf/m2_request/repository_intake.py: Workspace
#   - called by src/asf/m4_execution/worker/worker_graph.py: Workspace
#   - called by src/asf/m4_execution/verification/gate.py: Workspace
#   - called by src/asf/m4_execution/integration/integrator.py: Workspace
#   - called by tests/m5_shared/workspace/test_workspace.py: Workspace
#   - called by tests/m4_execution/worker/test_worker_graph.py: Workspace
#   - called by src/asf/m3_orchestration/run_graph.py: Workspace
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Call git via subprocess argument lists; locate git with shutil.which and fail with an actionable error if missing (doctor checks it).
#   9. Take a per-branch file lock through the platform adapter before mutating operations.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Return WorkspaceResult(ok=False, error_kind=...) for conflict/lock/io; raise AsfError only when git is missing.
# DONE WHEN: (1) tests/m5_shared/workspace/test_workspace.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/workspace/workspace.py` and `uv run mypy src/asf/m5_shared/workspace/workspace.py` are clean.

import logging
import shutil
from pathlib import Path
from typing import Any

from asf.contracts.workspace import WorkspaceOp, WorkspaceResult
from asf.m5_shared.workspace.blobs import BlobStore
from asf.platform.select import get_platform

logger = logging.getLogger(__name__)


class Workspace:
    repo_dir: Path
    git_bin: str
    blobs: BlobStore

    def __init__(self, repo_dir: Path, blobs: BlobStore | None = None) -> None:
        self.repo_dir = repo_dir
        git_found = shutil.which("git")
        if not git_found:
            raise RuntimeError("git binary not found in PATH")
        self.git_bin = git_found
        self.blobs = blobs if blobs is not None else BlobStore(repo_dir / ".asf_blobs")

    def _run_git(self, args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
        target_cwd = cwd if cwd is not None else self.repo_dir
        res = get_platform().run_process([self.git_bin, *args], cwd=target_cwd, timeout_s=60)
        stdout = res.stdout.decode("utf-8", errors="replace").strip()
        stderr = res.stderr.decode("utf-8", errors="replace").strip()
        return res.exit_code, stdout, stderr

    def _task_worktree(self, op: WorkspaceOp) -> Path | None:
        """The task's own worktree directory when it exists (reset and revert must act there, not on the main checkout)."""
        if op.task_id:
            candidate = self.repo_dir / ".worktrees" / str(op.task_id)
            if candidate.is_dir():
                return candidate
        return None

    def _apply_unlocked(self, op: WorkspaceOp, kind_val: str) -> WorkspaceResult:
        if kind_val == "create_worktree":
            branch = op.branch or (f"task/{op.task_id}" if op.task_id else "task/worktree")
            wt_dir = self.repo_dir / ".worktrees" / (op.task_id or op.branch or "worktree")
            wt_dir.parent.mkdir(parents=True, exist_ok=True)
            base = op.base_commit or "HEAD"

            code, out, err = self._run_git(["worktree", "add", "-b", branch, str(wt_dir), base])
            if code != 0:
                code, out, err = self._run_git(["worktree", "add", str(wt_dir), branch])
            if code != 0:
                return WorkspaceResult(ok=False, error_kind=f"worktree_failed: {err}")

            code, out, _ = self._run_git(["rev-parse", "HEAD"], cwd=wt_dir)
            return WorkspaceResult(ok=True, worktree_path=str(wt_dir), commit=out if code == 0 else base)

        if kind_val == "diff":
            base = op.base_commit or "HEAD"
            target = op.branch or "HEAD"
            code, out, err = self._run_git(["diff", base, target])
            if code != 0:
                code, out, err = self._run_git(["diff", base])
            diff_ref = self.blobs.put(out.encode("utf-8"))
            return WorkspaceResult(ok=True, diff_ref=diff_ref)

        if kind_val == "merge":
            if not op.branch:
                return WorkspaceResult(ok=False, error_kind="missing_branch")
            code, out, err = self._run_git(["merge", "--no-ff", "-m", f"Merge {op.branch}", op.branch])
            if code != 0:
                self._run_git(["merge", "--abort"])
                return WorkspaceResult(ok=False, error_kind="merge_conflict")
            code, out, _ = self._run_git(["rev-parse", "HEAD"])
            return WorkspaceResult(ok=True, commit=out if code == 0 else None)

        if kind_val == "revert":
            cwd = self._task_worktree(op)  # never discard changes in the main checkout when a task worktree exists
            code, out, err = self._run_git(["reset", "--hard", "HEAD"], cwd=cwd)
            if code != 0:
                return WorkspaceResult(ok=False, error_kind=f"revert_failed: {err}")
            if cwd is not None:
                self._run_git(["clean", "-fd"], cwd=cwd)
            code, out, _ = self._run_git(["rev-parse", "HEAD"], cwd=cwd)
            return WorkspaceResult(ok=True, commit=out if code == 0 else None)

        if kind_val == "tag":
            tag_name = op.branch or f"checkpoint-{op.task_id}"
            code, out, err = self._run_git(["tag", "-f", tag_name])
            if code != 0:
                return WorkspaceResult(ok=False, error_kind=f"tag_failed: {err}")
            code, out, _ = self._run_git(["rev-parse", "HEAD"])
            return WorkspaceResult(ok=True, commit=out if code == 0 else None)

        if kind_val == "reset_to_base":
            base = op.base_commit or "HEAD"
            cwd = self._task_worktree(op)
            code, out, err = self._run_git(["reset", "--hard", base], cwd=cwd)
            if code != 0:
                return WorkspaceResult(ok=False, error_kind=f"reset_failed: {err}")
            if cwd is not None:
                self._run_git(["clean", "-fd"], cwd=cwd)  # an interrupted attempt may have left untracked files
            return WorkspaceResult(ok=True, commit=base)

        return WorkspaceResult(ok=False, error_kind=f"unknown_op: {kind_val}")

    def apply(self, op: WorkspaceOp) -> WorkspaceResult:
        kind_val = op.kind.value if hasattr(op.kind, "value") else str(op.kind)

        # diff is non-mutating
        if kind_val == "diff":
            return self._apply_unlocked(op, kind_val)

        # Mutating operations take branch file lock
        lock_name = (op.branch or (f"task_{op.task_id}" if op.task_id else "main")).replace("/", "_")
        lock_path = self.repo_dir / ".asf_locks" / f"{lock_name}.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock_cm: Any = get_platform().lock_file(lock_path, timeout_s=10.0)
        except Exception as e:  # noqa: BLE001 - the lock backend raises platform-specific errors
            logger.warning("could not take the workspace lock %s", lock_path, exc_info=True)
            return WorkspaceResult(ok=False, error_kind=f"lock_failed: {e}")

        with lock_cm:
            return self._apply_unlocked(op, kind_val)

    def gc(self, keep_tagged: bool = True) -> int:
        code, out, _ = self._run_git(["worktree", "prune"])
        return 1 if code == 0 else 0
