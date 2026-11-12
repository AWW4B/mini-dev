# FILE: tests/cli/views/test_inbox_view.py
# ROLE: Tests that prove src/asf/cli/views/inbox_view.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02 Decision Inbox; IF-03; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/views/inbox_view.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/views/inbox_view.py: InboxView (unit under test)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (capture the output)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (a real store with rows)
#   - imports from src/asf/contracts/decisions.py: DecisionRequest (request fixtures)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (writes the pending decisions)
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use the tmp_path fixture or the fake_paths fixture for every filesystem location.
#   6. Use the fakes from tests/conftest.py instead of real GPUs, networks, sandboxes or model providers unless the test is marked needs_gpu, needs_network or needs_sandbox.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; real API keys; network access in unmarked tests; sleeping for timing (use the fake clock)
# ERRORS: Failures surface as pytest assertion failures.
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/views/test_inbox_view.py` on Windows and Linux once src/asf/cli/views/inbox_view.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/views/test_inbox_view.py` and `uv run mypy tests/cli/views/test_inbox_view.py` are clean.

import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from asf.cli.ui.render import OutputMode, Renderer
from asf.cli.views.inbox_view import InboxView
from asf.contracts.decisions import DecisionRequest
from asf.m5_shared.decisions.broker import DecisionBroker
from asf.m5_shared.state_store.store import StateStore


def _request(decision_id: str, run_id: str = "run1", **over: Any) -> DecisionRequest:
    base = {
        "decision_id": decision_id, "run_id": run_id, "kind": "clarify", "requester": "asf.m2", "question": f"Question {decision_id}?",
        "options": ["yes", "no"], "default_on_timeout": None, "evidence_refs": ["sha256:abc"],
    }
    return DecisionRequest.model_validate({**base, **over})


def _view(store: StateStore, run: str | None = "run1", mode: OutputMode = OutputMode.JSON, **kw: Any) -> tuple[InboxView, io.StringIO]:
    out = io.StringIO()
    return InboxView(Renderer(mode, stdout=out, stderr=io.StringIO()), run, store=store, **kw), out


def test_pending_decisions_are_listed_for_the_run(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "s.db")
    broker = DecisionBroker(store)
    broker.request(_request("d1"))
    broker.request(_request("d2", run_id="other"))
    view, out = _view(store)
    assert [d.decision_id for d in view.pending()] == ["d1"]
    view.render_once()
    doc = json.loads(out.getvalue())
    assert doc["rows"] == [{"id": "d1", "kind": "clarify", "question": "Question d1?", "options": "yes, no", "deadline": "-"}]


def test_without_a_run_filter_every_pending_decision_shows(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "s.db")
    broker = DecisionBroker(store)
    broker.request(_request("d1"))
    broker.request(_request("d2", run_id="other"))
    assert sorted(d.decision_id for d in _view(store, None)[0].pending()) == ["d1", "d2"]


def test_answered_decisions_disappear(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "s.db")
    with store.conn:
        store.conn.execute("INSERT INTO decisions (decision_id, run_id, topic, status, version, payload) VALUES ('d9', 'run1', 'clarify', 'RESOLVED', 1, '{}')")
    view, out = _view(store, mode=OutputMode.PLAIN)
    assert view.pending() == [] and view.card("d9") is None
    view.render_once()
    assert "No decisions are waiting" in out.getvalue()


def test_a_card_shows_question_options_default_deadline_and_evidence(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "s.db")
    deadline = datetime(2026, 12, 1, 10, 0, tzinfo=UTC)
    DecisionBroker(store).request(_request("d1", default_on_timeout="no", deadline=deadline))
    view, out = _view(store)
    card = view.card("d1")
    assert card is not None
    view.render_card(card)
    data = json.loads(out.getvalue())["data"]
    assert data["question"] == "Question d1?" and data["options"] == "yes, no" and data["if no answer"] == "no"
    assert data["deadline"] == deadline.isoformat() and data["evidence"] == "sha256:abc" and data["kind"] == "clarify"


def test_a_decision_without_a_default_says_the_subtree_stays_suspended(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "s.db")
    DecisionBroker(store).request(_request("d1"))
    view, out = _view(store)
    card = view.card("d1")
    assert card is not None
    view.render_card(card)
    assert "suspended" in json.loads(out.getvalue())["data"]["if no answer"]


def test_an_unknown_card_is_none(tmp_path: Path) -> None:
    assert _view(StateStore.open(tmp_path / "s.db"))[0].card("nope") is None


def test_live_exits_on_ctrl_c_and_leaves_decisions_pending(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "s.db")
    DecisionBroker(store).request(_request("d1"))

    def sleep(seconds: float) -> None:
        raise KeyboardInterrupt

    view, out = _view(store, mode=OutputMode.PLAIN, sleep=sleep)
    view.live()
    assert "view closed" in out.getvalue() and len(view.pending()) == 1
