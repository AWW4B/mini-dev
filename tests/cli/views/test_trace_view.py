# FILE: tests/cli/views/test_trace_view.py
# ROLE: Tests that prove src/asf/cli/views/trace_view.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02 Active Group Chat; IF-18; D-14; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/views/trace_view.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/views/trace_view.py: TraceView (unit under test)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (capture the output)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (a real store with rows)
#   - imports from src/asf/contracts/events.py: EventEnvelope (event fixtures)
#   - imports from src/asf/m5_shared/events/event_log.py: EventLog (stores the events)
#   - imports from src/asf/m5_shared/events/fanout.py: EventFanout (patched to end the live view)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/views/test_trace_view.py` on Windows and Linux once src/asf/cli/views/trace_view.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/views/test_trace_view.py` and `uv run mypy tests/cli/views/test_trace_view.py` are clean.

import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from asf.cli.ui.render import OutputMode, Renderer
from asf.cli.views.trace_view import TraceView
from asf.contracts.events import EventEnvelope
from asf.m5_shared.events.event_log import EventLog
from asf.m5_shared.events.fanout import EventFanout
from asf.m5_shared.state_store.store import StateStore


def _event(event_id: str, kind: str = "step_started", visibility: str = "user", task_id: str | None = None, **payload: Any) -> EventEnvelope:
    return EventEnvelope.model_validate(
        {
            "event_id": event_id, "run_id": "run1", "task_id": task_id, "seq": 0, "ts": datetime(2026, 11, 12, 10, 0, 5, tzinfo=UTC),
            "actor": {"kind": "agent", "role": "worker", "name": "Worker 1"}, "kind": kind, "correlation_id": "c", "payload": payload, "visibility": visibility,
        }
    )


def _setup(tmp_path: Path, *events: EventEnvelope) -> tuple[StateStore, EventLog]:
    store = StateStore.open(tmp_path / "s.db")
    with store.conn:
        store.conn.execute(
            "INSERT INTO runs (run_id, project_id, status, version, created_at, last_activity, cost, cost_estimated, payload) "
            "VALUES ('run1', 'p', 'RUNNING', 1, 't', 't', 0, 0, '{}')"
        )
    log = EventLog(store.conn)
    log.append(list(events))
    return store, log


def _view(store: StateStore, mode: OutputMode = OutputMode.JSON, **kw: Any) -> tuple[TraceView, io.StringIO]:
    out = io.StringIO()
    return TraceView(Renderer(mode, stdout=out, stderr=io.StringIO()), "run1", store=store, **kw), out


def _rows(out: io.StringIO) -> list[dict[str, Any]]:
    return [row for line in out.getvalue().splitlines() for row in json.loads(line)["rows"]]


def test_events_are_shown_in_seq_order_with_actor_kind_and_a_payload_summary(tmp_path: Path) -> None:
    store, _ = _setup(tmp_path, _event("e1", "task_received", goal_summary="build it"), _event("e2", "step_started", step_no=1))
    view, out = _view(store)
    assert view.render_once() == 2
    rows = _rows(out)
    assert [(r["seq"], r["who"], r["event"]) for r in rows] == [(1, "Worker 1", "task_received"), (2, "Worker 1", "step_started")]
    assert rows[0]["time"] == "10:00:05" and "build it" in rows[0]["details"]


def test_the_user_level_hides_internal_events_and_the_internal_level_shows_them(tmp_path: Path) -> None:
    store, _ = _setup(tmp_path, _event("e1"), _event("e2", "usage", visibility="internal"))
    view, out = _view(store, level="user")
    view.render_once()
    assert [r["event"] for r in _rows(out)] == ["step_started"]
    view2, out2 = _view(store, level="internal")
    view2.render_once()
    assert len(_rows(out2)) == 2


def test_a_task_filter_narrows_the_projection(tmp_path: Path) -> None:
    store, _ = _setup(tmp_path, _event("e1", task_id="t1"), _event("e2", task_id="t2"), _event("e3"))
    view, out = _view(store, task="t2")
    view.render_once()
    assert [r["task"] for r in _rows(out)] == ["t2"]


def test_calling_again_replays_only_what_is_new_from_the_cursor(tmp_path: Path) -> None:
    store, log = _setup(tmp_path, _event("e1"))
    view, out = _view(store)
    assert view.render_once() == 1
    log.append([_event("e2", "gate_result", passed=True)])
    assert view.render_once() == 2
    assert [r["seq"] for r in _rows(out)] == [1, 2]
    assert view.render_once() == 2 and len(_rows(out)) == 2  # nothing new, nothing printed


def test_long_payloads_are_shortened(tmp_path: Path) -> None:
    store, _ = _setup(tmp_path, _event("e1", note="x" * 500))
    view, out = _view(store)
    view.render_once()
    assert len(_rows(out)[0]["details"]) <= 120


def test_an_unknown_level_is_rejected(tmp_path: Path) -> None:
    store, _ = _setup(tmp_path)
    with pytest.raises(ValueError):
        TraceView(Renderer(OutputMode.JSON), "run1", level="debug", store=store)


def test_live_follows_new_events_until_ctrl_c(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, log = _setup(tmp_path, _event("e1"))
    out = io.StringIO()
    view = TraceView(Renderer(OutputMode.JSON, stdout=out, stderr=io.StringIO()), "run1", store=store, interval_s=0.0)

    def fake_follow(self: Any, run_id: str, after_seq: int, kinds: Any = None) -> Any:
        yield from log.read(run_id, after_seq)
        raise KeyboardInterrupt

    monkeypatch.setattr(EventFanout, "follow", fake_follow)
    view.live()
    assert [r["event"] for r in _rows(out)] == ["step_started"] and view.cursor == 1
