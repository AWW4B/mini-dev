# FILE: src/asf/m4_execution/worker/worker_graph.py
# ROLE: One attempt of the Local Coding Worker: worktree, ContextPack, bounded loop, ChangeSet to the gate. No checkpointer (D-05).
# ARCH REF: M4; p07 Local Coding Worker; IF-11; IF-12; IF-14; IF-15; IF-21 ChangeSet; D-05
# OWNS: Attempt lifecycle
# DOES NOT OWN: Pass/fail decisions (gate)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tasks.py: LeafTaskSpec (IF-09)
#   - imports from src/asf/contracts/outcomes.py: ChangeSet (IF-21)
#   - imports from src/asf/contracts/models.py: SlotLease (IF-13)
#   - imports from src/asf/m4_execution/worker/strategies.py: run_strategy (loop)
#   - imports from src/asf/m4_execution/verification/gate.py: verify_change_set (IF-21)
#   - imports from src/asf/m5_shared/workspace/workspace.py: Workspace (IF-15 git operations)
#   - imports from src/asf/m5_shared/context/context_service.py: ContextService (IF-11 ContextPack)
#   - imports from src/asf/contracts/context.py: ContextItem, ContextRequest (IF-11)
#   - imports from src/asf/contracts/errors.py: AsfError (base of WorkerError)
#   - imports from src/asf/contracts/workspace.py: WorkspaceOp (create_worktree, reset_to_base)
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (strategy model calls)
#   - imports from src/asf/m5_shared/tools/executor.py: ToolExecutor (strategy tool calls)
#   - called by src/asf/m4_execution/scheduler.py: run_attempt
#   - called by tests/m4_execution/worker/test_worker_graph.py: run_attempt, WorkerError
#   - called by src/asf/m3_orchestration/run_graph.py: run_attempt
#   - imports from src/asf/m5_shared/trace.py: trace_event (dependencies merged into a worktree)
#   - emits/consumes: emits TASK_RECEIVED, STEP_STARTED, HANDOFF_SENT (worker -> gate); tool events come from ToolExecutor
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Never resume an interrupted attempt; recovery resets the worktree and the scheduler re-dispatches (D-06).
#   9. Heartbeat the lease while running.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m4_execution/worker/test_worker_graph.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m4_execution/worker/worker_graph.py` and `uv run mypy src/asf/m4_execution/worker/worker_graph.py` are clean.

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from asf.contracts.context import ContextItem, ContextRequest
from asf.contracts.errors import AsfError
from asf.contracts.models import SlotLease
from asf.contracts.outcomes import ChangeSet
from asf.contracts.tasks import LeafTaskSpec
from asf.contracts.workspace import WorkspaceOp
from asf.m4_execution.worker.strategies import WorkerStrategyName, run_strategy
from asf.m5_shared.context.context_service import ContextService
from asf.m5_shared.gateway.gateway import ModelGateway
from asf.m5_shared.tools.executor import ToolExecutor
from asf.m5_shared.trace import trace_event
from asf.m5_shared.workspace.workspace import Workspace

logger = logging.getLogger(__name__)

Emit = Callable[[str, dict[str, Any]], None]
_MAX_FILE_CHARS = 20000
HELPER_FROM_ATTEMPT = 2  # attempt 1 is the small local coder; from attempt 2 the planner tier takes over the coding
HELPER_ROLE = "T3"


class WorkerError(AsfError):
    """The attempt could not even start (no worktree); the scheduler requeues it without charging the attempt."""


class _Heartbeat:
    """Keeps the slot lease alive while the attempt runs (D-06): a crashed worker stops beating and the lease expires."""

    def __init__(self, runtime: Any, lease: SlotLease) -> None:
        self._runtime = runtime
        self._lease_id = str(lease.lease_id)
        remaining = max(3.0, lease.expires_at_monotonic - time.monotonic())
        self._interval = max(1.0, remaining / 3)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._beat, name=f"heartbeat-{self._lease_id}", daemon=True)

    def _beat(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self._runtime.heartbeat(self._lease_id)
            except (KeyError, AsfError):  # LocalRuntime.heartbeat raises AsfError for an unknown or expired lease
                logger.warning("lease %s expired while the attempt was running", self._lease_id)
                return

    def __enter__(self) -> "_Heartbeat":
        if self._runtime is not None:
            self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)


def _create_worktree(workspace: Workspace, spec: LeafTaskSpec) -> str:
    task_id = str(spec.task_id)
    created = workspace.apply(
        WorkspaceOp.model_validate(
            {"kind": "create_worktree", "task_id": task_id, "branch": f"task/{task_id}", "base_commit": spec.base_commit}
        )
    )
    if created.ok and created.worktree_path:
        return created.worktree_path
    existing = workspace.repo_dir / ".worktrees" / task_id
    if existing.is_dir():  # a retry: wipe what the previous attempt left behind and start again
        reset = workspace.apply(WorkspaceOp.model_validate({"kind": "reset_to_base", "task_id": task_id, "base_commit": spec.base_commit}))
        if reset.ok:
            return str(existing)
    raise WorkerError(f"Could not create a worktree for task {task_id}: {created.error_kind}")


def _context_text(
    spec: LeafTaskSpec, lease: SlotLease, worktree: str, service: ContextService, failure_evidence: str | None, memory_items: list[ContextItem] | None = None
) -> str:
    """IF-11: assemble the ContextPack (spec, pinned capsules, allowed files, latest failure) under the token budget."""
    def add(tier: int, ref: str, text: str) -> None:
        service.add_item(ContextItem.model_validate({"tier": tier, "source_ref": ref, "sha256": "", "tokens": 0, "text": text}))

    add(0, "spec", f"{spec.goal}\nAcceptance tests: {', '.join(spec.acceptance_test_refs)}")
    for capsule in spec.capsules:
        add(1, f"capsule:{capsule.module_id}.{capsule.operation}", "\n".join(capsule.lines))
    for rel in [*spec.allowed_files, *spec.read_only_files]:
        path = Path(worktree) / rel
        if path.is_file():
            add(2, f"file:{rel}", path.read_text(encoding="utf-8", errors="replace")[:_MAX_FILE_CHARS])
    if failure_evidence:
        add(5, "latest-failure", failure_evidence[-4000:])
    for item in memory_items or []:  # chosen by the memory router under the role's layer budgets; optional tiers only
        service.add_item(item)
    pack = service.build(
        ContextRequest.model_validate(
            {"task_id": str(spec.task_id), "role": "coder", "budget_tokens": spec.context_budget_tokens, "model_id": lease.model_id}
        )
    )
    return "\n\n".join(f"## {item.source_ref}\n{item.text}" for item in pack.items)


_NOT_A_CHANGE = (":(exclude)**/__pycache__/**", ":(exclude)*.pyc", ":(exclude).pytest_cache/**", ":(exclude).mypy_cache/**", ":(exclude).ruff_cache/**")


def _merge_dependencies(workspace: Workspace, spec: LeafTaskSpec, worktree: str) -> str:
    """Bring the verified code of the tasks this one depends on into its worktree; return the commit its own changes are measured from.

    A leaf is cut from the commit it was certified at, which does not contain its dependencies' code (those live on their own task
    branches until the parent is integrated), so a cli task importing the core module failed on ImportError in every attempt.
    """
    wt = Path(worktree)
    for dep in getattr(spec, "depends_on", []):
        branch = f"task/{dep}"
        code, _, err = workspace._run_git(["-c", "user.name=ASF", "-c", "user.email=asf@factory.local", "merge", "--no-edit", branch], cwd=wt)
        if code != 0:
            workspace._run_git(["merge", "--abort"], cwd=wt)
            trace_event("worker", "dependency_not_merged", task=str(spec.task_id), dependency=dep, error=err)
        else:
            trace_event("worker", "dependency_merged", task=str(spec.task_id), dependency=dep)
    code, head, _ = workspace._run_git(["rev-parse", "HEAD"], cwd=wt)
    return head.strip() if code == 0 and head.strip() else spec.base_commit


def _commit_and_describe(workspace: Workspace, spec: LeafTaskSpec, worktree: str, attempt_no: int, base: str | None = None) -> tuple[str, list[str]]:
    """Commit the attempt on its task branch; return (diff blob ref, files touched since the base commit)."""
    wt = Path(worktree)
    # bytecode and test caches are by-products of running the tests, not changes: without this every attempt that ran a test was a policy violation
    workspace._run_git(["add", "-A", "--", ".", *_NOT_A_CHANGE], cwd=wt)
    code, status, _ = workspace._run_git(["status", "--porcelain"], cwd=wt)
    if code == 0 and status.strip():
        workspace._run_git(
            ["-c", "user.name=ASF Worker", "-c", "user.email=worker@asf.local", "commit", "-m", f"task {spec.task_id} attempt {attempt_no}"],
            cwd=wt,
        )
    start = base or spec.base_commit
    _, names, _ = workspace._run_git(["diff", "--name-only", start, "HEAD"], cwd=wt)
    _, diff, _ = workspace._run_git(["diff", start, "HEAD"], cwd=wt)
    return workspace.blobs.put(diff.encode("utf-8")), [n for n in names.splitlines() if n.strip()]


def run_attempt(
    spec: LeafTaskSpec,
    lease: SlotLease,
    attempt_no: int,
    *,
    workspace: Workspace,
    gateway: ModelGateway,
    executor: ToolExecutor,
    context_service: ContextService | None = None,
    runtime: Any = None,
    strategy: WorkerStrategyName = "tool_loop",
    failure_evidence: str | None = None,
    emit: Emit | None = None,
    memory_items: list[ContextItem] | None = None,
) -> ChangeSet:
    """One attempt: worktree -> ContextPack -> bounded strategy loop (lease kept alive) -> committed ChangeSet.

    Never resumes an interrupted attempt: a retry always starts from a clean worktree at the base commit.
    Raises ContextOverflow (must-have context too big), WorkerBlocked (model reports a gap) or WorkerError.
    """
    task_id = str(spec.task_id)

    def publish(kind: str, payload: dict[str, Any]) -> None:
        if emit is not None:
            emit(kind, {"task_id": task_id, "attempt_no": attempt_no, **payload})

    publish("TASK_RECEIVED", {"goal_summary": spec.goal[:200], "from_role": "scheduler"})
    worktree = _create_worktree(workspace, spec)
    base = _merge_dependencies(workspace, spec, worktree)
    service = context_service if context_service is not None else ContextService()
    context = _context_text(spec, lease, worktree, service, failure_evidence, memory_items)

    publish("STEP_STARTED", {"strategy": strategy, "summary": f"working in {worktree}"})
    with _Heartbeat(runtime, lease):
        helper = HELPER_ROLE if attempt_no >= HELPER_FROM_ATTEMPT else None
        if helper is not None:
            trace_event("worker", "helper_model", task=task_id, attempt=attempt_no, role=helper, why="the small coder did not pass in earlier attempts")
        report = run_strategy(strategy, spec, worktree, gateway=gateway, executor=executor, context=context, model_role=helper)

    diff_ref, touched = _commit_and_describe(workspace, spec, worktree, attempt_no, base)
    change = ChangeSet.model_validate(
        {
            "task_id": task_id,
            "attempt_no": attempt_no,
            "diff_ref": diff_ref,
            "worktree_path": worktree,
            "files_touched": touched,
            "self_report": report,
        }
    )
    publish("HANDOFF_SENT", {"to_role": "gate", "summary": f"{len(touched)} file(s) changed"})
    return change
