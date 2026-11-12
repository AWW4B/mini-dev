# FILE: src/asf/cli/views/dash_view.py
# ROLE: Live dashboard: VRAM/RAM, slots, tokens, cost (EST flags), queue, controls hint.
# ARCH REF: M1; p02 Resource Dashboard; IF-19; IF-20
# OWNS: Rendering this view
# DOES NOT OWN: Data production
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/metrics.py: MetricsSnapshot (IF-19)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: open_store, resolve_run_id (the project's store and the default run)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (read-only queries)
#   - imports from src/asf/m5_shared/metrics/collector.py: MetricsCollector (snapshot of the run's metrics)
#   - called by src/asf/cli/commands/dash.py: DashView
#   - called by tests/cli/views/test_dash_view.py: DashView
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Escape all agent/tool text before rendering; never execute or interpret it.
#   6. Refresh using cursors, not busy loops.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/cli/views/test_dash_view.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/views/dash_view.py` and `uv run mypy src/asf/cli/views/dash_view.py` are clean.

import time
from collections.abc import Callable
from typing import Any

import psutil

from asf.cli.context import open_store, resolve_run_id
from asf.contracts.metrics import MetricsSnapshot
from asf.m5_shared.metrics.collector import MetricsCollector
from asf.m5_shared.state_store.store import StateStore

_GB = 1024**3


class DashView:
    """Live dashboard: run status, the task queue, tokens and cost (flagged EST when estimated), memory, and the controls."""

    def __init__(
        self,
        renderer: Any,
        run_id: str | None,
        *,
        store: StateStore | None = None,
        interval_s: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.renderer = renderer
        self.run_id = run_id
        self._store = store
        self._interval_s = interval_s
        self._sleep = sleep

    def snapshot(self) -> tuple[str, MetricsSnapshot, dict[str, int], dict[str, Any], int]:
        store = self._store if self._store is not None else open_store(readonly=True)
        run_id = resolve_run_id(store, self.run_id)
        metrics = MetricsCollector(store).snapshot(run_id)
        queue = {str(r["state"]): int(r["n"]) for r in store.conn.execute("SELECT state, COUNT(*) AS n FROM tasks WHERE run_id = ? GROUP BY state", (run_id,))}
        run = store.conn.execute("SELECT project_id, status, cost, cost_estimated, last_activity FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        pending = int(store.conn.execute("SELECT COUNT(*) FROM decisions WHERE run_id = ? AND status = 'PENDING'", (run_id,)).fetchone()[0])
        info = dict(run) if run is not None else {}
        return run_id, metrics, queue, info, pending

    def render_once(self) -> None:
        run_id, metrics, queue, info, pending = self.snapshot()
        values, sources = metrics.values, metrics.sources
        cost_flag = " EST" if sources.get("cost") is not None and sources["cost"].value == "ESTIMATED" else ""
        memory = psutil.virtual_memory()
        self.renderer.record(
            f"Run {run_id}",
            {
                "status": info.get("status", "?"),
                "project": info.get("project_id", "?"),
                "last activity": info.get("last_activity", "?"),
                "calls": int(values.get("calls", 0)),
                "tokens in / out": f"{int(values.get('input_tokens', 0))} / {int(values.get('output_tokens', 0))}",
                "cost": f"{values.get('cost', 0.0):.4f}{cost_flag}",
                "RAM free": f"{memory.available / _GB:.1f} GB",
                "decisions waiting": pending,
                "controls": "factory run pause | resume | abort | cancel-task",
            },
        )
        self.renderer.table("Task queue", ["state", "tasks"], [[state, n] for state, n in sorted(queue.items())])

    def live(self) -> None:
        """Refresh until Ctrl+C (which only exits the view)."""
        try:
            while True:
                self.render_once()
                self._sleep(self._interval_s)
        except KeyboardInterrupt:
            self.renderer.message("view closed (the run keeps going)")
