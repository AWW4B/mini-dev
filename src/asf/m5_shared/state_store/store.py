# FILE: src/asf/m5_shared/state_store/store.py
# ROLE: Applies StateCommit transactions with optimistic concurrency and serves read queries over state.db.
# ARCH REF: M5; p09 Project State Store; IF-16 StateCommit; IF-24 HistoryQuery; IF-05 command table (D-15); D-05
# OWNS: All reads/writes of state.db, the command table, history queries
# DOES NOT OWN: The LangGraph checkpoints.db file; event fan-out (events/fanout.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/state.py: StateCommit (IF-16)
#   - imports from src/asf/contracts/history.py: HistoryQuery, HistoryResult (IF-24)
#   - imports from src/asf/contracts/tasks.py: TaskNode, TaskState (task records)
#   - imports from src/asf/contracts/control.py: RunControl (IF-05 command rows)
#   - imports from src/asf/m5_shared/state_store/schema.py: migrate (schema setup)
#   - imports from src/asf/contracts/errors.py: StateConflict (error types)
#   - called by src/asf/m5_shared/state_store/outbox.py: StateStore
#   - called by src/asf/m5_shared/state_store/recovery.py: StateStore
#   - called by src/asf/m5_shared/decisions/broker.py: StateStore
#   - called by src/asf/m5_shared/metrics/collector.py: StateStore
#   - called by src/asf/m5_shared/registry/registry.py: StateStore
#   - called by src/asf/m5_shared/context/memory.py: StateStore
#   - called by src/asf/m2_request/intake_router.py: StateStore
#   - called by src/asf/m3_orchestration/run_graph.py: StateStore
#   - called by src/asf/m3_orchestration/run_control.py: StateStore
#   - called by src/asf/m3_orchestration/escalation.py: StateStore
#   - called by src/asf/m3_orchestration/decomposition/frontier.py: StateStore
#   - called by src/asf/m4_execution/scheduler.py: StateStore
#   - called by src/asf/m4_execution/integration/integrator.py: StateStore
#   - called by src/asf/cli/commands/project.py: StateStore
#   - called by src/asf/cli/commands/history.py: StateStore
#   - called by src/asf/cli/commands/report.py: StateStore
#   - called by src/asf/cli/run_controls.py: StateStore
#   - called by tests/m5_shared/state_store/test_store.py: StateStore
#   - emits/consumes: writes outbox rows holding EventEnvelope (IF-17) in the same transaction as each mutation
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Open read-only connections with the SQLite URI mode=ro for viewers (CLI views, web viewer).
#   9. Every commit() runs in one transaction: check expected_version, apply the mutation, insert outbox events; raise StateConflict on mismatch.
#   10. Use file locking from the platform adapter only for the single-writer guard; never rely on OS signals.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: StateConflict for version mismatch; AsfError for I/O problems with the db path in the message.
# DONE WHEN: (1) tests/m5_shared/state_store/test_store.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/state_store/store.py` and `uv run mypy src/asf/m5_shared/state_store/store.py` are clean.

from pathlib import Path

from asf.contracts.control import RunControl
from asf.contracts.history import HistoryQuery, HistoryResult
from asf.contracts.state import StateCommit
from asf.contracts.tasks import TaskNode, TaskState


class StateStore:
    """Single writer for state.db (WAL). Readers open with readonly=True."""

    @classmethod
    def open(cls, db_path: Path, readonly: bool = False) -> "StateStore":
        raise NotImplementedError

    def commit(self, change: StateCommit) -> int:
        """Apply one IF-16 commit atomically; return the new entity version."""
        raise NotImplementedError

    def get_task(self, task_id: str) -> TaskNode:
        raise NotImplementedError

    def tasks_in_state(self, run_id: str, state: TaskState) -> list[TaskNode]:
        raise NotImplementedError

    def put_command(self, command: RunControl) -> None:
        """Insert an IF-05 command row (idempotent on command_id)."""
        raise NotImplementedError

    def poll_commands(self, run_id: str) -> list[RunControl]:
        """Return and mark consumed the unprocessed commands for a run."""
        raise NotImplementedError

    def history(self, query: HistoryQuery) -> HistoryResult:
        """Serve IF-24."""
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
