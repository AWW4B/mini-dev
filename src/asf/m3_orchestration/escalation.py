# FILE: src/asf/m3_orchestration/escalation.py
# ROLE: Handles escalated TaskOutcomes: re-split, re-plan, budget raise or user decision.
# ARCH REF: M3; p04 Escalation & Recovery; IF-10; A-3
# OWNS: Escalation policy
# DOES NOT OWN: Running attempts (M4)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/outcomes.py: TaskOutcome, FailureClass (IF-10)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (IF-03 decisions)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (IF-16 state)
#   - called by tests/m3_orchestration/test_escalation.py: handle_escalation
#   - emits/consumes: raises DecisionRequest kinds ESCALATION, BUDGET_RAISE, MANUAL_SPLIT
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/test_escalation.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/escalation.py` and `uv run mypy src/asf/m3_orchestration/escalation.py` are clean.

from asf.contracts.outcomes import TaskOutcome


def handle_escalation(outcome: TaskOutcome) -> str:
    """Return the action taken: 'resplit' | 'replan' | 'ask_user' | 'abandon'."""
    raise NotImplementedError
