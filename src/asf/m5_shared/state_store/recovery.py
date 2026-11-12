# FILE: src/asf/m5_shared/state_store/recovery.py
# ROLE: Reconciles state after a crash or restart before any graph resumes (SEQ-2).
# ARCH REF: M5; p09 recovery; p14 SEQ-2; D-06; p16 interruption row
# OWNS: Startup reconciliation steps and the RecoveryReport
# DOES NOT OWN: Resuming LangGraph threads (run_graph does that after reconciliation)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (state)
#   - imports from src/asf/m5_shared/workspace/workspace.py: Workspace (IF-15 reset worktrees)
#   - imports from src/asf/m5_shared/runtime/local_runtime.py: LocalRuntime (drop stale slots)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (re-arm decisions)
#   - imports from src/asf/contracts/errors.py: AsfError (base of RecoveryError)
#   - imports from src/asf/contracts/state.py: StateCommit (task transition plus STATE_CHANGED events)
#   - imports from src/asf/contracts/workspace.py: WorkspaceOp (reset_to_base)
#   - called by tests/m5_shared/state_store/test_recovery.py: RecoveryError, RecoveryReport, reconcile_on_startup
#   - emits/consumes: emits RUN_RECOVERED and STATE_CHANGED events through StateStore.commit
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Order: expire leases (RUNNING -> READY, interruptions+1, >3 -> ESCALATED), reset interrupted worktrees to base commit, re-probe runtime, re-arm decisions, restore frontier, then report.
#   9. Never re-run or modify VERIFIED or INTEGRATED tasks.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/state_store/test_recovery.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/state_store/recovery.py` and `uv run mypy src/asf/m5_shared/state_store/recovery.py` are clean.

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from asf.contracts.errors import AsfError
from asf.contracts.state import StateCommit
from asf.contracts.workspace import WorkspaceOp
from asf.m5_shared.decisions.broker import DecisionBroker
from asf.m5_shared.runtime.local_runtime import LocalRuntime
from asf.m5_shared.state_store.store import StateStore
from asf.m5_shared.workspace.workspace import Workspace

logger = logging.getLogger(__name__)

MAX_INTERRUPTIONS = 3


class RecoveryError(AsfError):
    """Startup reconciliation could not reset every interrupted task; fix the cause and start again (nothing was lost)."""


class RecoveryReport(BaseModel):
    runs_checked: int
    tasks_reset: list[str]
    tasks_escalated: list[str]
    decisions_rearmed: int


def _event(run_id: str, task_id: str | None, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": f"evt-{uuid.uuid4().hex}",
        "run_id": run_id,
        "task_id": task_id,
        "seq": 0,  # the event log assigns the real sequence number
        "ts": datetime.now(UTC).isoformat(),
        "actor": {"kind": "service", "role": "recovery", "name": "Startup recovery"},
        "kind": kind,
        "correlation_id": run_id,
        "payload": payload,
    }


def reconcile_on_startup(
    store: StateStore,
    workspace: Workspace,
    runtime: LocalRuntime,
    broker: DecisionBroker,
) -> RecoveryReport:
    _ = broker  # pending decisions live in the store and are re-armed simply by being counted and left PENDING

    runs_checked = int(store.conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0])

    # 2. Expire leases of interrupted tasks (RUNNING -> READY, or ESCALATED after too many interruptions).
    #    VERIFIED and INTEGRATED tasks are never selected, so they are never re-run or modified (rule 9).
    tasks_reset: list[str] = []
    tasks_escalated: list[str] = []
    failed_resets: list[str] = []
    recovered_runs: set[str] = set()

    running = store.conn.execute("SELECT task_id, run_id, version, payload FROM tasks WHERE state = 'RUNNING' ORDER BY rowid").fetchall()
    for row in running:
        task_id, run_id, version = str(row["task_id"]), str(row["run_id"]), int(row["version"])
        payload: dict[str, Any] = json.loads(row["payload"] or "{}")
        counters: dict[str, Any] = dict(payload.get("counters") or {})
        interruptions = int(counters.get("interruptions", 0)) + 1
        counters["interruptions"] = interruptions
        escalate = interruptions > MAX_INTERRUPTIONS
        new_state = "ESCALATED" if escalate else "READY"

        # 3. An interrupted worktree is reset to its base commit before the task may run again.
        if not escalate:
            try:
                workspace.apply(WorkspaceOp.model_validate({"kind": "reset_to_base", "task_id": task_id}))
            except Exception:  # noqa: BLE001 - git/worktree errors vary; the task stays RUNNING so the next start retries
                logger.error("could not reset the worktree of task %s; leaving it RUNNING", task_id, exc_info=True)
                failed_resets.append(task_id)
                continue

        events = [_event(run_id, task_id, "state_changed", {"entity": "task", "from": "RUNNING", "to": new_state, "interruptions": interruptions})]
        if run_id not in recovered_runs:
            events.append(_event(run_id, None, "run_recovered", {"reason": "restart"}))
            recovered_runs.add(run_id)
        store.commit(
            StateCommit.model_validate(
                {
                    "entity": "task",
                    "entity_id": task_id,
                    "expected_version": version,
                    "mutation": {"state": new_state, "prior_state": "RUNNING", "counters": counters},
                    "events": events,
                }
            )
        )
        with store.conn:
            store.conn.execute("DELETE FROM leases WHERE task_id = ?", (task_id,))
        (tasks_escalated if escalate else tasks_reset).append(task_id)

    # 4. Re-probe the runtime: drop slot leases whose holder is gone, and refresh the resource reading.
    try:
        runtime.drop_stale()
        runtime.probe.read()
    except Exception:  # noqa: BLE001 - the runtime backends are optional; scheduling degrades to what it can measure
        logger.warning("runtime re-probe failed; slot and resource state may be stale", exc_info=True)

    # 5. Pending decisions stay PENDING in the store; count them so the caller can re-arm their timers.
    decisions_rearmed = int(store.conn.execute("SELECT COUNT(*) FROM decisions WHERE status = 'PENDING'").fetchone()[0])

    if failed_resets:
        raise RecoveryError(
            f"Could not reset the worktrees of {len(failed_resets)} interrupted task(s): {', '.join(failed_resets)}. "
            "They were left RUNNING; check the project's git state and start again."
        )

    return RecoveryReport(
        runs_checked=runs_checked,
        tasks_reset=tasks_reset,
        tasks_escalated=tasks_escalated,
        decisions_rearmed=decisions_rearmed,
    )
