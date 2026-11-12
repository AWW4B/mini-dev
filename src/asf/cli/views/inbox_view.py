# FILE: src/asf/cli/views/inbox_view.py
# ROLE: Decision cards: question, options, default, deadline, evidence links.
# ARCH REF: M1; p02 Decision Inbox; IF-03
# OWNS: Rendering this view
# DOES NOT OWN: Data production
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/decisions.py: DecisionRequest (IF-03)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: open_store, resolve_run_id (the project's store and the default run)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (read-only queries)
#   - called by src/asf/cli/commands/inbox.py: InboxView
#   - called by tests/cli/views/test_inbox_view.py: InboxView
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
# DONE WHEN: (1) tests/cli/views/test_inbox_view.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/views/inbox_view.py` and `uv run mypy src/asf/cli/views/inbox_view.py` are clean.

import time
from collections.abc import Callable
from typing import Any

from asf.cli.context import open_store
from asf.contracts.decisions import DecisionRequest
from asf.m5_shared.state_store.store import StateStore


class InboxView:
    """Decision cards: the question, its options, the safe default, the deadline and the evidence links."""

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

    def pending(self) -> list[DecisionRequest]:
        store = self._store if self._store is not None else open_store(readonly=True)
        sql = "SELECT payload FROM decisions WHERE status = 'PENDING'"
        params: list[Any] = []
        if self.run_id:
            sql += " AND run_id = ?"
            params.append(self.run_id)
        return [DecisionRequest.model_validate_json(r["payload"]) for r in store.conn.execute(sql + " ORDER BY created_at, rowid", params)]

    def card(self, decision_id: str) -> DecisionRequest | None:
        store = self._store if self._store is not None else open_store(readonly=True)
        row = store.conn.execute("SELECT payload, status FROM decisions WHERE decision_id = ?", (decision_id,)).fetchone()
        if row is None or row["status"] != "PENDING":
            return None
        return DecisionRequest.model_validate_json(row["payload"])

    def render_card(self, request: DecisionRequest) -> None:
        self.renderer.record(
            f"Decision {request.decision_id}",
            {
                "kind": request.kind.value,
                "run": str(request.run_id),
                "task": str(request.task_id) if request.task_id else "-",
                "question": request.question,
                "options": ", ".join(request.options),
                "if no answer": request.default_on_timeout or "stays pending (the subtree is suspended)",
                "deadline": request.deadline.isoformat() if request.deadline else "none",
                "evidence": ", ".join(request.evidence_refs) or "-",
                "asked by": request.requester,
            },
        )

    def render_once(self) -> None:
        pending = self.pending()
        if not pending:
            self.renderer.message("No decisions are waiting for you.")
            return
        self.renderer.table(
            "Decisions waiting for you",
            ["id", "kind", "question", "options", "deadline"],
            [[d.decision_id, d.kind.value, d.question, ", ".join(d.options), d.deadline.isoformat() if d.deadline else "-"] for d in pending],
        )

    def live(self) -> None:
        """Refresh until Ctrl+C (which only exits the view)."""
        try:
            while True:
                self.render_once()
                self._sleep(self._interval_s)
        except KeyboardInterrupt:
            self.renderer.message("view closed (decisions stay pending)")
