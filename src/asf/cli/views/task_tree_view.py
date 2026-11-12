# FILE: src/asf/cli/views/task_tree_view.py
# ROLE: Task tree with node states, attempts and counters.
# ARCH REF: M1; p02; p06
# OWNS: Rendering this view
# DOES NOT OWN: Data production
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tasks.py: TaskNode (nodes)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: open_store, resolve_run_id (the project's store and the default run)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (read-only queries)
#   - called by src/asf/cli/commands/tasks.py: TaskTreeView
#   - called by tests/cli/views/test_task_tree_view.py: TaskTreeView
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
# DONE WHEN: (1) tests/cli/views/test_task_tree_view.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/views/task_tree_view.py` and `uv run mypy src/asf/cli/views/task_tree_view.py` are clean.

import json
import time
from collections.abc import Callable
from typing import Any

from asf.cli.context import open_store, resolve_run_id
from asf.contracts.tasks import TaskNode
from asf.m5_shared.state_store.store import StateStore


def _node_label(node: TaskNode) -> str:
    c = node.counters
    counters = f"attempts {c.attempts}/3" + (f", splits {c.split_attempts}" if c.split_attempts else "") + (f", repairs {c.repair_rounds}" if c.repair_rounds else "")
    return f"{node.id}: {node.goal[:70]} ({counters})"


class TaskTreeView:
    """The task tree of a run: node states, attempts and counters (read-only)."""

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

    def build(self) -> tuple[str, list[dict[str, Any]]]:
        store = self._store if self._store is not None else open_store(readonly=True)
        run_id = resolve_run_id(store, self.run_id)
        rows = store.conn.execute(
            "SELECT payload FROM tasks WHERE run_id = ? OR run_id LIKE ? ORDER BY rowid", (run_id, f"{run_id}-%")
        ).fetchall()
        nodes = {}
        for row in rows:
            node = TaskNode.model_validate(json.loads(row["payload"]))
            nodes[str(node.id)] = node
        children: dict[str, list[dict[str, Any]]] = {}
        entries: dict[str, dict[str, Any]] = {}
        for node_id, node in nodes.items():
            entries[node_id] = {"label": _node_label(node), "state": node.state.value, "children": children.setdefault(node_id, [])}
        roots: list[dict[str, Any]] = []
        for node_id, node in nodes.items():
            parent = str(node.parent_id) if node.parent_id is not None else None
            (children.setdefault(parent, []) if parent in nodes else roots).append(entries[node_id])
        return run_id, roots

    def render_once(self) -> None:
        run_id, roots = self.build()
        self.renderer.tree(f"Tasks of run {run_id}", roots)

    def live(self) -> None:
        """Refresh until Ctrl+C (which only exits the view)."""
        try:
            while True:
                self.render_once()
                self._sleep(self._interval_s)
        except KeyboardInterrupt:
            self.renderer.message("view closed (the run keeps going)")
