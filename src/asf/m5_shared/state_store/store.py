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
#   - called by tests/m5_shared/state_store/test_recovery.py: StateStore
#   - called by tests/m4_execution/integration/test_integrator.py: StateStore
#   - called by tests/m3_orchestration/decomposition/test_frontier.py: StateStore
#   - called by tests/m3_orchestration/test_run_control.py: StateStore
#   - called by tests/m3_orchestration/test_run_graph.py: StateStore
#   - called by tests/cli/test_run_controls.py: StateStore
#   - called by src/asf/cli/context.py: StateStore
#   - called by tests/cli/test_context.py: StateStore
#   - called by src/asf/cli/views/task_tree_view.py: StateStore
#   - called by src/asf/cli/views/inbox_view.py: StateStore
#   - called by src/asf/cli/views/trace_view.py: StateStore
#   - called by src/asf/cli/views/dash_view.py: StateStore
#   - called by tests/cli/views/test_task_tree_view.py: StateStore
#   - called by tests/cli/views/test_inbox_view.py: StateStore
#   - called by tests/cli/views/test_trace_view.py: StateStore
#   - called by tests/cli/views/test_dash_view.py: StateStore
#   - called by tests/conftest.py: StateStore
#   - called by src/asf/cli/commands/init.py: StateStore
#   - called by tests/cli/commands/test_project.py: StateStore
#   - called by tests/m3_orchestration/test_e2e.py: StateStore
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

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from asf.contracts.control import RunCommand, RunControl
from asf.contracts.errors import StateConflict
from asf.contracts.history import HistoryQuery, HistoryResult, RunSummary
from asf.contracts.state import StateCommit
from asf.contracts.tasks import TaskNode, TaskState
from asf.m5_shared.state_store.schema import migrate

_ENTITY_TABLE_MAP: dict[str, tuple[str, str]] = {
    "runs": ("runs", "run_id"),
    "run": ("runs", "run_id"),
    "tasks": ("tasks", "task_id"),
    "task": ("tasks", "task_id"),
    "attempts": ("attempts", "attempt_id"),
    "attempt": ("attempts", "attempt_id"),
    "leases": ("leases", "lease_id"),
    "lease": ("leases", "lease_id"),
    "decisions": ("decisions", "decision_id"),
    "decision": ("decisions", "decision_id"),
    "contracts": ("contracts", "contract_id"),
    "contract": ("contracts", "contract_id"),
}


class StateStore:
    """Single writer for state.db (WAL). Readers open with readonly=True."""

    conn: sqlite3.Connection
    db_path: Path
    readonly: bool

    def __init__(self, conn: sqlite3.Connection, db_path: Path, readonly: bool = False) -> None:
        self.conn = conn
        self.db_path = db_path
        self.readonly = readonly

    @classmethod
    def open(cls, db_path: Path, readonly: bool = False) -> "StateStore":
        if readonly:
            uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = 5000;")
            return cls(conn, db_path, readonly=True)

        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), autocommit=False)
        conn.row_factory = sqlite3.Row
        migrate(conn)
        return cls(conn, db_path, readonly=False)

    def commit(self, change: StateCommit) -> int:
        """Apply one IF-16 commit atomically; return the new entity version."""
        mapping = _ENTITY_TABLE_MAP.get(change.entity)
        if mapping is None:  # the table name is interpolated into SQL below, so only known entities may reach it
            raise ValueError(f"Unknown entity '{change.entity}'; expected one of {sorted(_ENTITY_TABLE_MAP)}")
        table, id_col = mapping
        now_iso = datetime.now(UTC).isoformat()

        with self.conn:
            cur = self.conn.execute(
                f"SELECT version, payload FROM {table} WHERE {id_col} = ?",  # noqa: S608
                (change.entity_id,),
            )
            row = cur.fetchone()

            current_version: int | None = None
            current_payload: dict[str, Any] = {}
            if row is not None:
                current_version = int(row["version"])
                raw_payload = row["payload"]
                if raw_payload:
                    current_payload = json.loads(raw_payload)

            if change.expected_version != current_version:
                raise StateConflict(
                    f"Expected version {change.expected_version} for {change.entity}:{change.entity_id}, "
                    f"found {current_version}"
                )

            new_version = (current_version or 0) + 1
            merged_payload = {**current_payload, **change.mutation}
            payload_str = json.dumps(merged_payload)

            if table == "tasks":
                run_id = str(merged_payload.get("run_id", ""))
                parent_id = merged_payload.get("parent_id")
                state = str(merged_payload.get("state", "PROPOSED"))
                kind = str(merged_payload.get("kind", "composite"))
                title = str(merged_payload.get("title", merged_payload.get("goal", "")))
                if current_version is None:
                    self.conn.execute(
                        "INSERT INTO tasks (task_id, run_id, parent_id, state, kind, version, title, payload, "
                        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (change.entity_id, run_id, parent_id, state, kind, new_version, title, payload_str,
                         now_iso, now_iso),
                    )
                else:
                    self.conn.execute(
                        "UPDATE tasks SET version = ?, state = ?, payload = ?, updated_at = ? WHERE task_id = ?",
                        (new_version, state, payload_str, now_iso, change.entity_id),
                    )
            elif table == "runs":
                project_id = str(merged_payload.get("project_id", ""))
                status = str(merged_payload.get("status", "PENDING"))
                cost = float(merged_payload.get("cost", 0.0))
                cost_est = int(bool(merged_payload.get("cost_estimated", False)))
                if current_version is None:
                    self.conn.execute(
                        "INSERT INTO runs (run_id, project_id, status, version, created_at, last_activity, cost, "
                        "cost_estimated, payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (change.entity_id, project_id, status, new_version, now_iso, now_iso, cost, cost_est,
                         payload_str),
                    )
                else:
                    # A mutation that does not mention status, cost or cost_estimated must leave the stored values alone.
                    self.conn.execute(
                        "UPDATE runs SET version = ?, status = coalesce(?, status), last_activity = ?, "
                        "cost = coalesce(?, cost), cost_estimated = coalesce(?, cost_estimated), payload = ? "
                        "WHERE run_id = ?",
                        (
                            new_version,
                            str(change.mutation["status"]) if "status" in change.mutation else None,
                            now_iso,
                            float(change.mutation["cost"]) if "cost" in change.mutation else None,
                            int(bool(change.mutation["cost_estimated"])) if "cost_estimated" in change.mutation else None,
                            payload_str,
                            change.entity_id,
                        ),
                    )
            else:
                if current_version is None:
                    self.conn.execute(
                        f"INSERT INTO {table} ({id_col}, version, payload, created_at) VALUES (?, ?, ?, ?)",  # noqa: S608
                        (change.entity_id, new_version, payload_str, now_iso),
                    )
                else:
                    self.conn.execute(
                        f"UPDATE {table} SET version = ?, payload = ? WHERE {id_col} = ?",  # noqa: S608
                        (new_version, payload_str, change.entity_id),
                    )

            # Insert outbox events in the same transaction
            for event in change.events:
                self.conn.execute(
                    "INSERT OR IGNORE INTO outbox (event_id, run_id, payload, published, created_at) "
                    "VALUES (?, ?, ?, 0, ?)",
                    (event.event_id, event.run_id, event.model_dump_json(), now_iso),
                )

        return new_version

    def get_task(self, task_id: str) -> TaskNode:
        cur = self.conn.execute("SELECT payload FROM tasks WHERE task_id = ?", (task_id,))
        row = cur.fetchone()
        if row is None:
            raise KeyError(f"Task not found: {task_id}")
        return TaskNode.model_validate_json(row["payload"])

    def tasks_in_state(self, run_id: str, state: TaskState) -> list[TaskNode]:
        cur = self.conn.execute(
            "SELECT payload FROM tasks WHERE run_id = ? AND state = ? ORDER BY rowid ASC",
            (run_id, state.value if hasattr(state, "value") else str(state)),
        )
        return [TaskNode.model_validate_json(row["payload"]) for row in cur.fetchall()]

    def put_command(self, command: RunControl) -> None:
        """Insert an IF-05 command row (idempotent on command_id)."""
        now_iso = datetime.now(UTC).isoformat()
        cmd_val = command.command.value if hasattr(command.command, "value") else str(command.command)
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO commands (command_id, run_id, command, task_id, consumed, created_at) "
                "VALUES (?, ?, ?, ?, 0, ?)",
                (command.command_id, command.run_id, cmd_val, command.task_id, now_iso),
            )

    def poll_commands(self, run_id: str) -> list[RunControl]:
        """Return and mark consumed the unprocessed commands for a run."""
        with self.conn:
            cur = self.conn.execute(
                "SELECT command_id, run_id, command, task_id FROM commands "
                "WHERE run_id = ? AND consumed = 0 ORDER BY rowid ASC",
                (run_id,),
            )
            rows = cur.fetchall()
            commands: list[RunControl] = []
            for row in rows:
                commands.append(
                    RunControl(
                        command_id=row["command_id"],
                        run_id=row["run_id"],
                        command=RunCommand(row["command"]),
                        task_id=row["task_id"],
                    )
                )
            if rows:
                self.conn.execute("UPDATE commands SET consumed = 1 WHERE run_id = ? AND consumed = 0", (run_id,))
        return commands

    def history(self, query: HistoryQuery) -> HistoryResult:
        """Serve IF-24."""
        sql = "SELECT run_id, project_id, status, last_activity, cost, cost_estimated FROM runs WHERE 1=1"
        params: list[Any] = []
        if query.project_id:
            sql += " AND project_id = ?"
            params.append(query.project_id)
        if query.run_id:
            sql += " AND run_id = ?"
            params.append(query.run_id)
        sql += " ORDER BY last_activity DESC LIMIT ?"
        params.append(query.limit)

        cur = self.conn.execute(sql, params)
        summaries: list[RunSummary] = []
        for row in cur.fetchall():
            summaries.append(
                RunSummary(
                    run_id=row["run_id"],
                    project_id=row["project_id"],
                    status=row["status"],
                    last_activity=row["last_activity"],
                    cost=float(row["cost"]),
                    cost_estimated=bool(row["cost_estimated"]),
                )
            )
        return HistoryResult(runs=summaries)

    def close(self) -> None:
        self.conn.close()
