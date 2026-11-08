# FILE: src/asf/m5_shared/decisions/broker.py
# ROLE: Persists DecisionRequests with deadlines and safe defaults, and routes DecisionResolved back to the requester.
# ARCH REF: M5; p10 Decision Broker; p02 Decision Inbox; IF-03; IF-04; D-10; D-21; D-22
# OWNS: Pending decisions, deadlines, safe-default application, decision log entries
# DOES NOT OWN: Rendering cards (cli/views/inbox_view.py); LangGraph interrupt/resume (the requesting graph)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/decisions.py: DecisionRequest, DecisionResolved, NEVER_AUTO_APPROVED (IF-03/IF-04)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (persistence)
#   - called by src/asf/m5_shared/state_store/recovery.py: DecisionBroker
#   - called by src/asf/m5_shared/registry/registry.py: DecisionBroker
#   - called by src/asf/m5_shared/tools/executor.py: DecisionBroker
#   - called by src/asf/m2_request/document_ingestion.py: DecisionBroker
#   - called by src/asf/m2_request/request_understanding.py: DecisionBroker
#   - called by src/asf/m3_orchestration/run_graph.py: DecisionBroker
#   - called by src/asf/m3_orchestration/escalation.py: DecisionBroker
#   - called by src/asf/m3_orchestration/planning/test_authoring.py: DecisionBroker
#   - called by src/asf/m3_orchestration/planning/planner_graph.py: DecisionBroker
#   - called by src/asf/cli/commands/inbox.py: DecisionBroker
#   - called by tests/m5_shared/decisions/test_broker.py: DecisionBroker
#   - emits/consumes: emits DECISION_NEEDED and DECISION_RESOLVED events (EventEnvelope) through StateStore.commit
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Write the pending decision to state.db BEFORE the requesting graph calls interrupt().
#   6. Never apply a default for kinds in NEVER_AUTO_APPROVED; keep them pending and keep only their subtree suspended.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/decisions/test_broker.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/decisions/broker.py` and `uv run mypy src/asf/m5_shared/decisions/broker.py` are clean.

from asf.contracts.decisions import DecisionRequest, DecisionResolved
from asf.m5_shared.state_store.store import StateStore


class DecisionBroker:
    def __init__(self, store: StateStore) -> None:
        raise NotImplementedError

    def request(self, req: DecisionRequest) -> None:
        raise NotImplementedError

    def resolve(self, answer: DecisionResolved) -> None:
        """Validate the answer for its kind, log it, and mark it for routing to the requester."""
        raise NotImplementedError

    def pending(self, run_id: str | None = None) -> list[DecisionRequest]:
        raise NotImplementedError

    def sweep_deadlines(self) -> list[DecisionResolved]:
        """Apply safe defaults for expired decisions that allow them; return what was applied."""
        raise NotImplementedError
