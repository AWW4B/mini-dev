# FILE: src/asf/m3_orchestration/decomposition/frontier.py
# ROLE: The persisted priority frontier: push, pop highest-priority ready node, park and wake DEFERRED nodes.
# ARCH REF: M3; p05 persisted frontier; D-06 (batched loop, recursion_limit never the terminator)
# OWNS: Frontier ordering and persistence
# DOES NOT OWN: Sizing and splitting
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tasks.py: TaskNode (nodes)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (IF-16 state)
#   - imports from src/asf/contracts/state.py: StateCommit (write-through task rows)
#   - imports from src/asf/m3_orchestration/lifecycle.py: transition (PROPOSED/DEFERRED edges)
#   - called by src/asf/m3_orchestration/decomposition/decomposition_graph.py: Frontier
#   - called by tests/m3_orchestration/decomposition/test_frontier.py: Frontier
#   - called by tests/m3_orchestration/decomposition/test_decomposition_graph.py: Frontier
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/decomposition/test_frontier.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/decomposition/frontier.py` and `uv run mypy src/asf/m3_orchestration/decomposition/frontier.py` are clean.

import logging

from asf.contracts.state import StateCommit
from asf.contracts.tasks import TaskNode, TaskState
from asf.m3_orchestration.lifecycle import transition
from asf.m5_shared.state_store.store import StateStore

logger = logging.getLogger(__name__)


class Frontier:
    """The priority work-list of nodes waiting to be sized.

    With a StateStore every change is written through to the task rows, and a new Frontier for the same run reloads
    PROPOSED, DEFERRED and interrupted SIZING nodes, so a restarted run continues where it stopped. Without a store the
    frontier lives in memory only.
    """

    def __init__(self, run_id: str, store: StateStore | None = None) -> None:
        self.run_id = run_id
        self._store = store
        self._ready: dict[str, TaskNode] = {}  # PROPOSED, waiting to be popped
        self._inflight: dict[str, TaskNode] = {}  # popped, being sized or split
        self._deferred: dict[str, TaskNode] = {}  # parked until their dependencies are verified
        self._order: dict[str, int] = {}
        self._verified: set[str] = set()
        if store is not None:
            self._load(store)

    # -- persistence ----------------------------------------------------------------------------------------------

    def _load(self, store: StateStore) -> None:
        rows = store.conn.execute(
            "SELECT payload FROM tasks WHERE run_id = ? AND state IN ('PROPOSED', 'DEFERRED', 'SIZING') ORDER BY rowid", (self.run_id,)
        ).fetchall()
        for row in rows:
            node = TaskNode.model_validate_json(row["payload"])
            self._order[str(node.id)] = len(self._order)
            if node.state is TaskState.DEFERRED:
                self._deferred[str(node.id)] = node
            else:
                self._ready[str(node.id)] = node.model_copy(update={"state": TaskState.PROPOSED})  # an interrupted SIZING is re-sized

    def _persist(self, node: TaskNode) -> None:
        if self._store is None:
            return
        row = self._store.conn.execute("SELECT version FROM tasks WHERE task_id = ?", (str(node.id),)).fetchone()
        self._store.commit(
            StateCommit.model_validate(
                {
                    "entity": "task",
                    "entity_id": str(node.id),
                    "expected_version": int(row["version"]) if row is not None else None,
                    "mutation": node.model_dump(mode="json"),
                }
            )
        )

    def _dep_done(self, dep: str) -> bool:
        if dep in self._verified:
            return True
        if self._store is None:
            return False
        row = self._store.conn.execute("SELECT state FROM tasks WHERE task_id = ?", (dep,)).fetchone()
        return row is not None and row["state"] in ("VERIFIED", "INTEGRATED")

    def get(self, node_id: str) -> TaskNode | None:
        """The node by id: from the frontier, or from the store (for example an ESCALATED node that must be re-split)."""
        for bucket in (self._ready, self._inflight, self._deferred):
            if node_id in bucket:
                return bucket[node_id]
        if self._store is None:
            return None
        row = self._store.conn.execute("SELECT payload FROM tasks WHERE task_id = ?", (node_id,)).fetchone()
        return TaskNode.model_validate_json(row["payload"]) if row is not None else None

    def _known(self, node_id: str) -> bool:
        return node_id in self._order

    # -- the work-list --------------------------------------------------------------------------------------------

    def push(self, nodes: list[TaskNode]) -> None:
        """Add PROPOSED nodes; a node id that was pushed before is ignored (the duplicate guard)."""
        for node in nodes:
            if node.state is not TaskState.PROPOSED:
                raise ValueError(f"Only PROPOSED nodes can enter the frontier; {node.id} is {node.state.value}")
            if self._known(str(node.id)):
                logger.debug("node %s is already known to the frontier", node.id)
                continue
            self._order[str(node.id)] = len(self._order)
            self._persist(node)
            self._ready[str(node.id)] = node

    def pop_batch(self, max_nodes: int) -> list[TaskNode]:
        """Up to ``max_nodes`` nodes, highest priority first (priority, then shallower depth, then age)."""
        ranked = sorted(self._ready.values(), key=lambda n: (-n.priority, n.depth, self._order[str(n.id)]))[: max(0, max_nodes)]
        for node in ranked:
            del self._ready[str(node.id)]
            self._inflight[str(node.id)] = node
        return ranked

    def update(self, node: TaskNode) -> None:
        """Record a node's new state after the engine worked on it; a node that is PROPOSED again re-enters the frontier."""
        node_id = str(node.id)
        self._inflight.pop(node_id, None)
        self._ready.pop(node_id, None)
        self._deferred.pop(node_id, None)
        self._order.setdefault(node_id, len(self._order))
        self._persist(node)
        if node.state is TaskState.PROPOSED:
            self._ready[node_id] = node
        elif node.state is TaskState.DEFERRED:
            self._deferred[node_id] = node

    def park(self, node_id: str) -> None:
        """Lazy expansion: park a node as DEFERRED until its dependencies are verified."""
        node = self._inflight.get(node_id) or self._ready.get(node_id)
        if node is None:
            raise KeyError(f"Node {node_id} is not waiting in the frontier")
        self.update(transition(node, TaskState.DEFERRED, "lazy: later"))

    def wake_dependents(self, verified_task_id: str) -> int:
        """A task was verified: move DEFERRED nodes whose dependencies are all verified back to PROPOSED."""
        self._verified.add(verified_task_id)
        woken = 0
        for node in list(self._deferred.values()):
            if all(self._dep_done(str(dep)) for dep in node.deps):
                self.update(transition(node, TaskState.PROPOSED, f"dependency {verified_task_id} verified"))
                woken += 1
        return woken

    # -- observation ----------------------------------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._ready) + len(self._inflight)

    def deferred_ids(self) -> list[str]:
        return sorted(self._deferred)

    def is_verified(self, task_id: str) -> bool:
        return task_id in self._verified
