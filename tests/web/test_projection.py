# FILE: tests/web/test_projection.py
# ROLE: Tests that prove src/asf/web/projection.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02 Active Group Chat; IF-18; D-14b; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/web/projection.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/web/projection.py: Participant, Projection (unit under test)
#   - imports from src/asf/contracts/events.py: EventEnvelope (event fixtures)
#   - imports from src/asf/m5_shared/events/event_log.py: EventLog (stores the events)
#   - imports from src/asf/m5_shared/state_store/schema.py: migrate (a real database layout)
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (detail blobs)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/web/test_projection.py` on Windows and Linux once src/asf/web/projection.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/web/test_projection.py` and `uv run mypy tests/web/test_projection.py` are clean.

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from asf.contracts.events import EventEnvelope
from asf.m5_shared.events.event_log import EventLog
from asf.m5_shared.state_store.schema import migrate
from asf.m5_shared.workspace.blobs import BlobStore
from asf.web.projection import Participant, Projection


def _event(event_id: str, kind: str, name: str, role: str, payload: dict[str, Any] | None = None, **over: Any) -> EventEnvelope:
    return EventEnvelope.model_validate(
        {
            "event_id": event_id, "run_id": "run1", "seq": 0, "ts": "2026-11-12T10:00:00+00:00",
            "actor": {"kind": "agent", "role": role, "name": name, "model_tier": over.pop("tier", None)}, "kind": kind, "correlation_id": "c",
            "payload": payload or {}, **over,
        }
    )


def _db(tmp_path: Path, *events: EventEnvelope) -> Path:
    path = tmp_path / ".factory" / "state.db"
    path.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(path), autocommit=False)
    conn.row_factory = sqlite3.Row
    migrate(conn)
    with conn:
        conn.execute(
            "INSERT INTO runs (run_id, project_id, status, version, created_at, last_activity, cost, cost_estimated, payload) VALUES ('run1', 'p', 'RUNNING', 1, 't', 't', 0, 0, '{}')"
        )
    EventLog(conn).append(list(events))
    conn.close()
    return path


STORY = (
    _event("e1", "task_received", "Planner", "planner", {"goal_summary": "plan it", "from_role": "user"}, tier="T3"),
    _event("e2", "step_started", "Worker 1", "worker", {"step_no": 1, "strategy": "tool_loop", "summary": "go"}, task_id="t1", tier="T2"),
    _event("e3", "usage", "Worker 1", "worker", {"tokens_in": 5}, visibility="internal"),
    _event("e4", "gate_result", "Gate", "gate", {"passed": True, "summary": "all green"}, task_id="t1"),
)


def test_participant_model() -> None:
    p = Participant(key="W", role="worker", colour="#fff", avatar="WO", model_tier=None, current_task=None, last_result=None)
    assert p.role == "worker"


def test_participants_are_everyone_who_acted_with_tier_task_and_last_result(tmp_path: Path) -> None:
    view = Projection("run1", db_path=_db(tmp_path, *STORY))
    by_key = {p.key: p for p in view.participants()}
    assert list(by_key) == ["Planner", "Worker 1", "Gate"]
    assert by_key["Planner"].model_tier == "T3" and by_key["Worker 1"].current_task == "t1" and by_key["Worker 1"].model_tier == "T2"
    assert by_key["Gate"].last_result == "gate passed: all green"
    view.close()


def test_colour_and_avatar_are_deterministic_from_the_role(tmp_path: Path) -> None:
    a = Projection("run1", db_path=_db(tmp_path / "a", *STORY))
    b = Projection("run1", db_path=_db(tmp_path / "b", *STORY))
    assert [(p.colour, p.avatar) for p in a.participants()] == [(p.colour, p.avatar) for p in b.participants()]
    assert {p.avatar for p in a.participants()} == {"PL", "WO", "GA"}
    a.close()
    b.close()


def test_a_page_has_items_handoffs_participants_status_and_a_cursor(tmp_path: Path) -> None:
    view = Projection("run1", db_path=_db(tmp_path, *STORY))
    page = view.page(0)
    assert page["run_id"] == "run1" and page["status"] == "RUNNING"
    assert [i["kind"] for i in page["items"]] == ["task_received", "step_started", "gate_result"]  # the internal usage event is hidden
    assert page["next_seq"] == 4 and page["more"] is False
    assert len(page["participants"]) == 3 and page["handoffs"] == []
    view.close()


def test_internal_events_can_be_included(tmp_path: Path) -> None:
    view = Projection("run1", db_path=_db(tmp_path, *STORY))
    assert len(view.page(0, include_internal=True)["items"]) == 3  # usage is plumbing, not narrative, so it never becomes an item
    view.close()


def test_paging_resumes_from_the_cursor(tmp_path: Path) -> None:
    view = Projection("run1", db_path=_db(tmp_path, *STORY))
    first = view.page(0, limit=2)
    assert first["more"] is True and first["next_seq"] == 2
    second = view.page(first["next_seq"], limit=2)
    assert [i["seq"] for i in second["items"]] == [4] and second["next_seq"] == 4  # seq 3 was filtered but the cursor moved over it
    assert view.page(4)["items"] == [] and view.page(4)["next_seq"] == 4
    view.close()


def test_a_limit_is_clamped(tmp_path: Path) -> None:
    view = Projection("run1", db_path=_db(tmp_path, *STORY))
    assert len(view.page(0, limit=0)["items"]) <= 1
    view.close()


def test_the_latest_run_is_used_when_none_is_named(tmp_path: Path) -> None:
    view = Projection(None, db_path=_db(tmp_path, *STORY))
    assert view.run_id == "run1"
    view.close()


def test_the_database_is_opened_read_only(tmp_path: Path) -> None:
    view = Projection("run1", db_path=_db(tmp_path, *STORY))
    with pytest.raises(sqlite3.OperationalError):
        view._conn.execute("INSERT INTO meta VALUES ('x', 'y')")
    view.close()


def test_a_missing_database_or_run_is_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="factory init"):
        Projection("run1", db_path=tmp_path / "nope.db")
    path = tmp_path / ".factory" / "state.db"
    path.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(path))
    migrate(conn)
    conn.close()
    with pytest.raises(LookupError):
        Projection(None, db_path=path)


def test_details_are_blobs_redacted_and_size_capped(tmp_path: Path) -> None:
    blobs = BlobStore(tmp_path / "blobs")
    sample = "sk-abcdefghijklmnopqrstuvwxyz0123"
    ref = blobs.put(f"diff --git a/x\n+KEY = '{sample}'\n".encode())
    big = blobs.put(b"x" * 300_000)
    view = Projection("run1", db_path=_db(tmp_path, *STORY), blobs=blobs)
    detail = view.detail(ref)
    assert sample not in detail["text"] and "diff --git" in detail["text"] and detail["truncated"] is False
    capped = view.detail(big)
    assert capped["truncated"] is True and len(capped["text"]) == 200_000 and capped["bytes"] == 300_000
    view.close()


def test_bad_or_missing_detail_references_are_reported_not_raised(tmp_path: Path) -> None:
    view = Projection("run1", db_path=_db(tmp_path, *STORY), blobs=BlobStore(tmp_path / "blobs"))
    assert "error" in view.detail("../../etc/passwd") and "error" in view.detail("sha256:" + "0" * 64)
    view.close()
