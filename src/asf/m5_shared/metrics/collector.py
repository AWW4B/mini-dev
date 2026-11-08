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

from asf.contracts.metrics import CallMetric, LimitEvent, MetricsSnapshot, ToolMetric
from asf.m5_shared.state_store.store import StateStore


class MetricsCollector:
    def __init__(self, store: StateStore) -> None:
        raise NotImplementedError

    def record_call(self, metric: CallMetric) -> None:
        raise NotImplementedError

    def record_tool(self, metric: ToolMetric) -> None:
        raise NotImplementedError

    def record_limit(self, event: LimitEvent) -> None:
        raise NotImplementedError

    def snapshot(self, run_id: str | None) -> MetricsSnapshot:
        raise NotImplementedError

    def export_csv(self, run_id: str, dest_dir: "object") -> list[str]:
        """Write call/tool/limit tables as CSV files (D-25); dest_dir is a pathlib.Path."""
        raise NotImplementedError
