# FILE: src/asf/m3_orchestration/lifecycle.py
# ROLE: Encodes the task-node state machine: the only legal transitions and their guards.
# ARCH REF: M3; p06 Task node lifecycle; A-3
# OWNS: ALLOWED_TRANSITIONS and transition validation
# DOES NOT OWN: Persisting transitions (StateStore)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tasks.py: TaskNode, TaskState (states)
#   - imports from src/asf/contracts/errors.py: StateConflict (illegal transitions)
#   - called by src/asf/m3_orchestration/decomposition/decomposition_graph.py: transition
#   - called by tests/m3_orchestration/test_lifecycle.py: transition, ALLOWED_TRANSITIONS
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. ALLOWED_TRANSITIONS must match drawio page 06 edge-for-edge; any non-terminal state may go to SUSPENDED or CANCELLED.
#   6. Attempts < max_attempts -> READY; exhausted -> ESCALATED or re-split (A-3).
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/test_lifecycle.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/lifecycle.py` and `uv run mypy src/asf/m3_orchestration/lifecycle.py` are clean.

from asf.contracts.tasks import TaskNode, TaskState

ALLOWED_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {}


def transition(node: TaskNode, to: TaskState, reason: str) -> TaskNode:
    """Return an updated copy or raise StateConflict for an illegal edge."""
    raise NotImplementedError
