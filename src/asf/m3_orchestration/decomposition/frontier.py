# FILE: src/asf/m3_orchestration/decomposition/frontier.py
# ROLE: The persisted priority frontier: push, pop highest-priority ready node, park and wake DEFERRED nodes.
# ARCH REF: M3; p05 persisted frontier; D-06 (batched loop, recursion_limit never the terminator)
# OWNS: Frontier ordering and persistence
# DOES NOT OWN: Sizing and splitting
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tasks.py: TaskNode (nodes)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (IF-16 state)
#   - called by src/asf/m3_orchestration/decomposition/decomposition_graph.py: Frontier
#   - called by tests/m3_orchestration/decomposition/test_frontier.py: Frontier
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/decomposition/test_frontier.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/decomposition/frontier.py` and `uv run mypy src/asf/m3_orchestration/decomposition/frontier.py` are clean.

from asf.contracts.tasks import TaskNode


class Frontier:
    def __init__(self, run_id: str) -> None:
        raise NotImplementedError

    def push(self, nodes: list[TaskNode]) -> None:
        raise NotImplementedError

    def pop_batch(self, max_nodes: int) -> list[TaskNode]:
        raise NotImplementedError

    def park(self, node_id: str) -> None:
        raise NotImplementedError

    def wake_dependents(self, verified_task_id: str) -> int:
        raise NotImplementedError
