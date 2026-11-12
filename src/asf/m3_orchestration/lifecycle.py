# FILE: src/asf/m3_orchestration/lifecycle.py
# ROLE: Encodes the task-node state machine: the only legal transitions and their guards.
# ARCH REF: M3; p06 Task node lifecycle; A-3
# OWNS: ALLOWED_TRANSITIONS and transition validation
# DOES NOT OWN: Persisting transitions (StateStore)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tasks.py: TaskNode, TaskState (states)
#   - imports from src/asf/contracts/errors.py: StateConflict (illegal transitions)
#   - called by src/asf/m3_orchestration/decomposition/decomposition_graph.py: transition
#   - called by tests/m3_orchestration/test_lifecycle.py: transition, ALLOWED_TRANSITIONS, MAX_ATTEMPTS
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

from asf.contracts.errors import StateConflict
from asf.contracts.tasks import TaskNode, TaskState

S = TaskState

MAX_ATTEMPTS = 3  # worker attempts per leaf (A-3)
MAX_SPLIT_ATTEMPTS = 3  # 2 attempts + 1 higher-tier escalation
MAX_RESPLITS = 1  # re-splits after an execution failure
MAX_REPAIR_ROUNDS = 2
MAX_INTERRUPTIONS = 3

# States nothing leaves (pause and abort do not apply to them either).
_FINAL = frozenset({S.VERIFIED, S.INTEGRATED, S.CANCELLED, S.ABANDONED})

# The edges of drawio page 06. Composite nodes travel the top row, leaves the third row.
_EDGES: dict[TaskState, frozenset[TaskState]] = {
    S.PROPOSED: frozenset({S.SIZING, S.DEFERRED}),  # popped | lazy: later
    S.DEFERRED: frozenset({S.PROPOSED, S.SIZING}),  # dependency verified
    S.SIZING: frozenset({S.SPLITTING, S.LEAF_CERTIFIED, S.AWAITING_INPUT}),  # too big | fits | ambiguous
    S.AWAITING_INPUT: frozenset({S.SIZING, S.SPLITTING}),  # answered
    S.SPLITTING: frozenset({S.SPLITTING, S.DECOMPOSED, S.AWAITING_INPUT, S.ESCALATED}),  # retry | committed | split budget out
    S.DECOMPOSED: frozenset({S.CHILDREN_DONE}),  # all children done
    S.CHILDREN_DONE: frozenset({S.INTEGRATING}),
    S.INTEGRATING: frozenset({S.INTEGRATED, S.REPAIRING}),  # green | failed
    S.REPAIRING: frozenset({S.INTEGRATING, S.ESCALATED}),  # patched | rounds out
    S.LEAF_CERTIFIED: frozenset({S.BLOCKED, S.READY}),  # deps pending | deps verified
    S.BLOCKED: frozenset({S.READY}),
    S.READY: frozenset({S.RUNNING}),  # lease
    S.RUNNING: frozenset({S.VERIFYING, S.READY, S.ESCALATED}),  # change set | infra / interrupted | too many interruptions
    S.VERIFYING: frozenset({S.VERIFIED, S.FAILED_ATTEMPT, S.SPLITTING}),  # gates pass | LOCAL_BUG | SPEC_TOO_LARGE
    S.FAILED_ATTEMPT: frozenset({S.READY, S.ESCALATED, S.SPLITTING}),  # attempts < 3 | exhausted | re-split
    S.ESCALATED: frozenset({S.SIZING, S.SPLITTING, S.READY, S.ABANDONED}),  # re-planned / budget added | user abandons
    S.SUSPENDED: frozenset(),  # filled below: restore the prior state, or CANCELLED
    S.VERIFIED: frozenset(),
    S.INTEGRATED: frozenset(),
    S.CANCELLED: frozenset(),
    S.ABANDONED: frozenset(),
}

_NON_FINAL = frozenset(s for s in TaskState if s not in _FINAL)


def _build() -> dict[TaskState, frozenset[TaskState]]:
    edges = dict(_EDGES)
    for state in _NON_FINAL:
        if state is S.SUSPENDED:
            edges[state] = frozenset((_NON_FINAL - {S.SUSPENDED}) | {S.CANCELLED})  # resume restores any prior state
        else:
            edges[state] = edges[state] | {S.SUSPENDED, S.CANCELLED}  # pause / abort from any non-final state
    return edges


ALLOWED_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = _build()


def transition(node: TaskNode, to: TaskState, reason: str) -> TaskNode:
    """Return an updated copy or raise StateConflict for an illegal edge.

    Counters on the node bound every loop: entering RUNNING charges an attempt (<= 3) unless the previous run was lost to
    infrastructure ("infra..." / "interrupted..." reasons), SPLITTING charges a split attempt (<= 3) or, after an execution
    failure, the single re-split, and a run lost to interruptions more than 3 times must be ESCALATED.
    """
    current = node.state
    if to not in ALLOWED_TRANSITIONS[current]:
        raise StateConflict(f"Task {node.id}: illegal transition {current.value} -> {to.value} ({reason or 'no reason given'})")

    counters = node.counters.model_copy()
    prior = node.prior_state

    if current is S.SUSPENDED and to is not S.CANCELLED:
        if prior is not None and to is not prior:
            raise StateConflict(f"Task {node.id}: a suspended task resumes into {prior.value}, not {to.value}")
        prior = None
    if to is S.SUSPENDED:
        prior = current

    lost = reason.lower().startswith(("infra", "interrupted"))
    if to is S.RUNNING:
        if counters.attempts >= MAX_ATTEMPTS:
            raise StateConflict(f"Task {node.id}: all {MAX_ATTEMPTS} attempts are used; escalate or re-split")
        counters.attempts += 1
    elif current is S.RUNNING and to is S.READY:
        if not lost:
            raise StateConflict(f"Task {node.id}: RUNNING -> READY is only for infrastructure or interruption losses, got '{reason}'")
        counters.attempts = max(0, counters.attempts - 1)  # no attempt is charged for a lost run
        if reason.lower().startswith("interrupted"):
            counters.interruptions += 1
            if counters.interruptions > MAX_INTERRUPTIONS:
                raise StateConflict(f"Task {node.id}: interrupted more than {MAX_INTERRUPTIONS} times; escalate")
    elif current is S.FAILED_ATTEMPT and to is S.READY and counters.attempts >= MAX_ATTEMPTS:
        raise StateConflict(f"Task {node.id}: attempts exhausted ({counters.attempts}/{MAX_ATTEMPTS}); escalate or re-split")
    elif to is S.SPLITTING:
        if current in (S.VERIFYING, S.FAILED_ATTEMPT, S.ESCALATED):
            if counters.resplits >= MAX_RESPLITS:
                raise StateConflict(f"Task {node.id}: the re-split budget ({MAX_RESPLITS}) is used")
            counters.resplits += 1
        else:
            if counters.split_attempts >= MAX_SPLIT_ATTEMPTS:
                raise StateConflict(f"Task {node.id}: split attempts exhausted ({MAX_SPLIT_ATTEMPTS})")
            counters.split_attempts += 1
    elif to is S.REPAIRING and counters.repair_rounds > MAX_REPAIR_ROUNDS:
        raise StateConflict(f"Task {node.id}: repair rounds exhausted ({MAX_REPAIR_ROUNDS})")

    return node.model_copy(update={"state": to, "prior_state": prior, "counters": counters})
