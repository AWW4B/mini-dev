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

from pathlib import Path

from asf.contracts.workspace import WorkspaceOp, WorkspaceResult


class Workspace:
    def __init__(self, repo_dir: Path) -> None:
        raise NotImplementedError

    def apply(self, op: WorkspaceOp) -> WorkspaceResult:
        raise NotImplementedError

    def gc(self, keep_tagged: bool = True) -> int:
        raise NotImplementedError
