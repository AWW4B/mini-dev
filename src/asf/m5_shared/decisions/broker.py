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

import json
from datetime import UTC, datetime
from typing import Any

from asf.contracts.decisions import NEVER_AUTO_APPROVED, DecisionRequest, DecisionResolved
from asf.m5_shared.state_store.store import StateStore


class DecisionBroker:
    store: StateStore
    resolved_answers: dict[str, DecisionResolved]

    def __init__(self, store: StateStore) -> None:
        self.store = store
        self.resolved_answers = {}

    def request(self, req: DecisionRequest) -> None:
        topic = req.kind.value if hasattr(req.kind, "value") else str(req.kind)
        payload_str = req.model_dump_json() if hasattr(req, "model_dump_json") else json.dumps(req.__dict__)
        now_iso = datetime.now(UTC).isoformat()
        with self.store.conn:
            self.store.conn.execute(
                "INSERT OR IGNORE INTO decisions (decision_id, run_id, task_id, topic, status, version, "
                "payload, created_at) VALUES (?, ?, ?, ?, 'PENDING', 1, ?, ?)",
                (req.decision_id, req.run_id, req.task_id, topic, payload_str, now_iso),
            )

    def resolve(self, answer: DecisionResolved) -> None:
        """Validate the answer for its kind, log it, and mark it for routing to the requester."""
        cur = self.store.conn.execute(
            "SELECT payload, status FROM decisions WHERE decision_id = ?",
            (answer.decision_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise KeyError(f"Decision not found: {answer.decision_id}")
        if row["status"] == "RESOLVED":
            return  # at-least-once delivery: answering twice is harmless and must not overwrite the first answer

        req_data = json.loads(row["payload"])
        req = DecisionRequest.model_validate(req_data)

        if req.options and answer.choice not in req.options:
            raise ValueError(f"Invalid choice '{answer.choice}'. Allowed options: {req.options}")

        try:
            req_dump = req.model_dump(mode="json")
        except TypeError:
            req_dump = req.model_dump() if hasattr(req, "model_dump") else json.loads(json.dumps(req.__dict__, default=str))

        try:
            ans_dump = answer.model_dump(mode="json")
        except TypeError:
            ans_dump = (
                answer.model_dump()
                if hasattr(answer, "model_dump")
                else json.loads(json.dumps(answer.__dict__, default=str))
            )
        resolved_payload = {
            "request": req_dump,
            "resolution": ans_dump,
        }
        with self.store.conn:
            self.store.conn.execute(
                "UPDATE decisions SET status = 'RESOLVED', payload = ? WHERE decision_id = ?",
                (json.dumps(resolved_payload), answer.decision_id),
            )

        self.resolved_answers[answer.decision_id] = answer

    def pending(self, run_id: str | None = None) -> list[DecisionRequest]:
        sql = "SELECT payload FROM decisions WHERE status = 'PENDING'"
        params: list[Any] = []
        if run_id:
            sql += " AND run_id = ?"
            params.append(run_id)
        sql += " ORDER BY created_at ASC"

        cur = self.store.conn.execute(sql, params)
        requests: list[DecisionRequest] = []
        for row in cur.fetchall():
            requests.append(DecisionRequest.model_validate_json(row["payload"]))
        return requests

    def sweep_deadlines(self) -> list[DecisionResolved]:
        """Apply safe defaults for expired decisions that allow them; return what was applied."""
        now = datetime.now(UTC)
        pending_requests = self.pending()
        applied: list[DecisionResolved] = []

        for req in pending_requests:
            if req.deadline is None:
                continue

            deadline = req.deadline
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=UTC)

            if now >= deadline:
                # Never auto-approve kinds in NEVER_AUTO_APPROVED
                kind_val = req.kind.value if hasattr(req.kind, "value") else str(req.kind)
                never_auto_vals = {
                    k.value if hasattr(k, "value") else str(k) for k in NEVER_AUTO_APPROVED
                }
                if req.kind in NEVER_AUTO_APPROVED or kind_val in never_auto_vals:
                    continue

                if req.default_on_timeout is None:
                    continue

                answer = DecisionResolved(
                    decision_id=req.decision_id,
                    choice=req.default_on_timeout,
                    text="Applied safe default on deadline expiration",
                    answered_by="system",
                    answered_at=now,
                    applied_default=True,
                )
                self.resolve(answer)
                applied.append(answer)

        return applied
