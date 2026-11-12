# FILE: src/asf/m3_orchestration/escalation.py
# ROLE: Handles escalated TaskOutcomes: re-split, re-plan, budget raise or user decision.
# ARCH REF: M3; p04 Escalation & Recovery; IF-10; A-3
# OWNS: Escalation policy
# DOES NOT OWN: Running attempts (M4)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/outcomes.py: TaskOutcome, FailureClass (IF-10)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (IF-03 decisions)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (IF-16 state)
#   - imports from src/asf/contracts/decisions.py: DecisionRequest (ESCALATION / BUDGET_RAISE / MANUAL_SPLIT requests)
#   - called by tests/m3_orchestration/test_escalation.py: handle_escalation
#   - called by src/asf/m3_orchestration/run_graph.py: handle_escalation
#   - emits/consumes: raises DecisionRequest kinds ESCALATION, BUDGET_RAISE, MANUAL_SPLIT
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/test_escalation.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/escalation.py` and `uv run mypy src/asf/m3_orchestration/escalation.py` are clean.

import logging
from typing import Any

from asf.contracts.decisions import DecisionRequest
from asf.contracts.outcomes import FailureClass, TaskOutcome
from asf.m5_shared.decisions.broker import DecisionBroker
from asf.m5_shared.state_store.store import StateStore

logger = logging.getLogger(__name__)

MAX_REPLANS = 2

_ANSWER_TO_ACTION = {
    "replan": "replan",
    "raise_budget": "replan",
    "resplit": "resplit",
    "accept_larger_leaf": "resplit",
    "abandon_subtree": "abandon",
    "abort_run": "abandon",
}
_SIZE_CLASSES = (FailureClass.SPEC_TOO_LARGE, FailureClass.CONTEXT_OVERFLOW)
_CONTRACT_CLASSES = (FailureClass.CONTRACT_MISMATCH, FailureClass.CONTRACT_GAP)


def _ask(broker: DecisionBroker | None, run_id: str, task_id: str, kind: str, question: str, options: list[str], evidence: str | None) -> str | None:
    """Put the question to the user once (idempotent) and return their answer as an action, or None while pending."""
    if broker is None:
        logger.warning("escalation of %s needs a decision (%s) but no DecisionBroker is attached", task_id, kind)
        return None
    decision_id = f"dec-esc-{task_id}-{kind}"
    answered = broker.resolved_answers.get(decision_id)
    if answered is not None:
        return _ANSWER_TO_ACTION.get(str(answered.choice))
    broker.request(
        DecisionRequest.model_validate(
            {
                "decision_id": decision_id,
                "run_id": run_id,
                "task_id": task_id,
                "kind": kind,
                "requester": "asf.m3_orchestration.escalation",
                "question": question,
                "options": options,
                "default_on_timeout": None,  # no answer means the subtree stays suspended
                "evidence_refs": [evidence] if evidence else [],
            }
        )
    )
    return None


def _run_id_of(store: StateStore | None, task_id: str) -> str:
    if store is None:
        return task_id
    try:
        return str(store.get_task(task_id).run_id)
    except KeyError:
        return task_id


def handle_escalation(
    outcome: TaskOutcome,
    *,
    store: StateStore | None = None,
    broker: DecisionBroker | None = None,
    budget_left: bool = True,
    replans_done: int = 0,
    resplits_done: int = 0,
) -> str:
    """Return the action taken: 'resplit' | 'replan' | 'ask_user' | 'abandon'.

    Size problems are re-split once; contract and worker failures re-plan the subtree (at most twice, while the run budget
    lasts); everything else, and every exhausted budget, goes to the user through the DecisionBroker. A user's earlier answer
    is honoured, so calling this again after they decided returns their choice.
    """
    task_id = str(outcome.task_id)
    run_id = _run_id_of(store, task_id)
    failure: Any = outcome.failure_class
    evidence = outcome.evidence_ref

    def ask_user(kind: str, question: str, options: list[str]) -> str:
        return _ask(broker, run_id, task_id, kind, question, options, evidence) or "ask_user"

    if not budget_left:
        return ask_user("budget_raise", f"The run budget is exhausted while task {task_id} needs another round ({failure.value}). Raise it?", ["raise_budget", "abort_run"])
    if failure in _SIZE_CLASSES:
        if resplits_done < 1:
            return "resplit"
        return ask_user("manual_split", f"Task {task_id} is still too large after a re-split ({failure.value}). How should it continue?", ["accept_larger_leaf", "abandon_subtree"])
    if failure in _CONTRACT_CLASSES or failure in (FailureClass.ESCALATED, FailureClass.LOCAL_BUG, FailureClass.FLAKY, FailureClass.POLICY_VIOLATION):
        if replans_done < MAX_REPLANS:
            return "replan"
        return ask_user("escalation", f"Task {task_id} keeps failing ({failure.value}) after {replans_done} re-plans. What now?", ["replan", "abandon_subtree", "abort_run"])
    # ENV_INFRA and anything unforeseen: a person has to look at the environment.
    return ask_user("escalation", f"Task {task_id} stopped on a problem the system cannot fix itself ({failure.value}).", ["replan", "abandon_subtree", "abort_run"])
