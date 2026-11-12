# FILE: src/asf/m5_shared/metrics/collector.py
# ROLE: Records call, tool and limit metrics and builds MetricsSnapshots.
# ARCH REF: M5; p10 Metrics; IF-19 MetricsSnapshot; D-24; D-19 comparability
# OWNS: call_metrics, tool_metrics, limit_events rows and snapshots
# DOES NOT OWN: Thresholds (advisories.py); rendering (cli dash_view)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/metrics.py: CallMetric, ToolMetric, LimitEvent, MetricsSnapshot (metric shapes)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (persistence)
#   - called by src/asf/m5_shared/gateway/usage_callback.py: MetricsCollector
#   - called by src/asf/m5_shared/tools/executor.py: MetricsCollector
#   - called by src/asf/cli/commands/events.py: MetricsCollector
#   - called by src/asf/cli/commands/stats.py: MetricsCollector
#   - called by tests/m5_shared/metrics/test_collector.py: MetricsCollector
#   - called by src/asf/cli/views/dash_view.py: MetricsCollector
#   - emits/consumes: emits USAGE and LIMIT_HIT events
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. tool_loop and code_exec strategies must produce identical ToolMetric columns.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/metrics/test_collector.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/metrics/collector.py` and `uv run mypy src/asf/m5_shared/metrics/collector.py` are clean.

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from asf.contracts.metrics import CallMetric, LimitEvent, MetricsSnapshot, ToolMetric, ValueSource
from asf.m5_shared.state_store.store import StateStore


class MetricsCollector:
    store: StateStore

    def __init__(self, store: StateStore) -> None:
        self.store = store

    def record_call(self, metric: CallMetric) -> None:
        now_iso = datetime.now(UTC).isoformat()
        src_val = metric.source.value if hasattr(metric.source, "value") else str(metric.source)
        is_estimated = 1 if src_val == "ESTIMATED" else 0

        with self.store.conn:
            self.store.conn.execute(
                "INSERT INTO call_metrics (run_id, task_id, provider, model, input_tokens, output_tokens, "
                "cost, duration_ms, timestamp, role, strategy, estimated, retry_no) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    metric.run_id,
                    metric.task_id,
                    metric.provider,
                    metric.model,
                    metric.tokens_in,
                    metric.tokens_out,
                    metric.cost,
                    metric.latency_ms,
                    now_iso,
                    metric.role,
                    metric.strategy,
                    is_estimated,
                    metric.retry_no,
                ),
            )
            self.store.conn.execute(
                "UPDATE runs SET cost = cost + ?, cost_estimated = max(cost_estimated, ?) WHERE run_id = ?",
                (metric.cost, is_estimated, metric.run_id),
            )

    def record_tool(self, metric: ToolMetric) -> None:
        now_iso = datetime.now(UTC).isoformat()
        status_str = str(metric.exit_status).lower()
        success = 1 if status_str in ("0", "success", "ok") else 0

        with self.store.conn:
            self.store.conn.execute(
                "INSERT INTO tool_metrics (run_id, task_id, tool_name, duration_ms, success, timestamp, strategy, approval, "
                "sandbox_tier, exit_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (metric.run_id, metric.task_id, metric.tool, metric.duration_ms, success, now_iso, metric.strategy, metric.approval,
                 metric.sandbox_tier, str(metric.exit_status)),
            )

    def record_limit(self, event: LimitEvent) -> None:
        now_iso = datetime.now(UTC).isoformat()
        with self.store.conn:
            self.store.conn.execute(
                "INSERT INTO limit_events (run_id, kind, details, timestamp) VALUES (?, ?, ?, ?)",
                (event.run_id, event.kind, event.detail, now_iso),
            )

    def snapshot(self, run_id: str | None) -> MetricsSnapshot:
        call_sql = "SELECT coalesce(sum(cost), 0.0), coalesce(sum(input_tokens), 0), coalesce(sum(output_tokens), 0), count(*) FROM call_metrics"
        tool_sql = "SELECT count(*), coalesce(sum(duration_ms), 0) FROM tool_metrics"
        limit_sql = "SELECT count(*) FROM limit_events"
        params: list[Any] = []

        if run_id is not None:
            call_sql += " WHERE run_id = ?"
            tool_sql += " WHERE run_id = ?"
            limit_sql += " WHERE run_id = ?"
            params.append(run_id)

        cur = self.store.conn.execute(call_sql, params)
        call_row = cur.fetchone()
        tot_cost = float(call_row[0]) if call_row else 0.0
        tot_in = float(call_row[1]) if call_row else 0.0
        tot_out = float(call_row[2]) if call_row else 0.0
        tot_calls = float(call_row[3]) if call_row else 0.0

        cur = self.store.conn.execute(tool_sql, params)
        tool_row = cur.fetchone()
        tot_tools = float(tool_row[0]) if tool_row else 0.0

        cur = self.store.conn.execute(limit_sql, params)
        limit_row = cur.fetchone()
        tot_limits = float(limit_row[0]) if limit_row else 0.0

        values: dict[str, float] = {
            "cost": tot_cost,
            "input_tokens": tot_in,
            "output_tokens": tot_out,
            "calls": tot_calls,
            "tools": tot_tools,
            "limits": tot_limits,
        }

        # Check if cost was estimated
        estimated = False
        if run_id is not None:
            cur = self.store.conn.execute("SELECT cost_estimated FROM runs WHERE run_id = ?", (run_id,))
            run_row = cur.fetchone()
            if run_row and int(run_row[0]) == 1:
                estimated = True

        sources: dict[str, ValueSource] = {
            k: ValueSource.MEASURED for k in values
        }
        if estimated:
            sources["cost"] = ValueSource.ESTIMATED

        return MetricsSnapshot(
            run_id=cast(Any, run_id),
            values=values,
            sources=sources,
            advisories=[],
        )

    def export_csv(self, run_id: str, dest_dir: object) -> list[str]:
        """Write call/tool/limit tables as CSV files (D-25); dest_dir is a pathlib.Path."""
        target_dir = Path(str(dest_dir))
        target_dir.mkdir(parents=True, exist_ok=True)
        created_files: list[str] = []

        # 1. calls.csv
        calls_path = target_dir / "calls.csv"
        cur = self.store.conn.execute(
            "SELECT id, run_id, task_id, provider, model, input_tokens, output_tokens, cost, "
            "duration_ms, timestamp FROM call_metrics WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        )
        with calls_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "run_id", "task_id", "provider", "model", "input_tokens",
                "output_tokens", "cost", "duration_ms", "timestamp",
            ])
            for r in cur:
                writer.writerow(list(r))
        created_files.append(calls_path.as_posix())

        # 2. tools.csv
        tools_path = target_dir / "tools.csv"
        cur = self.store.conn.execute(
            "SELECT id, run_id, task_id, tool_name, duration_ms, success, timestamp "
            "FROM tool_metrics WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        )
        with tools_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "run_id", "task_id", "tool_name", "duration_ms", "success", "timestamp"])
            for r in cur:
                writer.writerow(list(r))
        created_files.append(tools_path.as_posix())

        # 3. limits.csv
        limits_path = target_dir / "limits.csv"
        cur = self.store.conn.execute(
            "SELECT id, run_id, kind, details, timestamp FROM limit_events WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        )
        with limits_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "run_id", "kind", "details", "timestamp"])
            for r in cur:
                writer.writerow(list(r))
        created_files.append(limits_path.as_posix())

        return created_files
