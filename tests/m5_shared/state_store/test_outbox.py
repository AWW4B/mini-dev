# FILE: tests/m5_shared/state_store/test_outbox.py
# ROLE: Tests that prove src/asf/m5_shared/state_store/outbox.py meets its DONE WHEN conditions.
# ARCH REF: M5; p09 outbox; IF-17; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/state_store/outbox.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/state_store/outbox.py: OutboxRelay (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/state_store/test_outbox.py` on Windows and Linux once src/asf/m5_shared/state_store/outbox.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/state_store/test_outbox.py` and `uv run mypy tests/m5_shared/state_store/test_outbox.py` are clean.

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from asf.m5_shared.state_store.outbox import OutboxRelay


def test_outbox_relay_meets_contract(tmp_path: Path) -> None:
    """Prove OutboxRelay behaves as declared in src/asf/m5_shared/state_store/outbox.py."""
    db_file = tmp_path / "test_outbox.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            run_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            published INTEGER NOT NULL DEFAULT 0,
            created_at TEXT
        );
        """
    )
    conn.commit()

    evt1 = {
        "event_id": "evt-1",
        "run_id": "run-1",
        "seq": 0,
        "ts": "2026-11-08T12:00:00Z",
        "actor": {"kind": "agent", "role": "worker", "name": "Worker 1"},
        "kind": "step_started",
        "correlation_id": "c1",
        "payload": {"step": 1},
        "visibility": "user",
    }
    evt2 = {
        "event_id": "evt-2",
        "run_id": "run-1",
        "seq": 0,
        "ts": "2026-11-08T12:01:00Z",
        "actor": {"kind": "service", "role": "system", "name": "Supervisor"},
        "kind": "run_completed",
        "correlation_id": "c1",
        "payload": {"status": "ok"},
        "visibility": "internal",
    }

    conn.execute(
        "INSERT INTO outbox (event_id, run_id, payload, published, created_at) VALUES (?, ?, ?, 0, ?)",
        ("evt-1", "run-1", json.dumps(evt1), "2026-11-08T12:00:00Z"),
    )
    conn.execute(
        "INSERT INTO outbox (event_id, run_id, payload, published, created_at) VALUES (?, ?, ?, 0, ?)",
        ("evt-2", "run-1", json.dumps(evt2), "2026-11-08T12:01:00Z"),
    )
    conn.commit()

    relayed_events: list[Any] = []

    class FakeEventLog:
        def append(self, events: list[Any]) -> list[int]:
            relayed_events.extend(events)
            return list(range(1, len(events) + 1))

    fake_store = SimpleNamespace(conn=conn)
    fake_log = FakeEventLog()

    relay = OutboxRelay(store=fake_store, log=fake_log)  # type: ignore[arg-type]

    # Relay pending rows
    count = relay.relay_once(max_rows=10)
    assert count == 2
    assert len(relayed_events) == 2

    # Check published status in outbox
    cur = conn.execute("SELECT published FROM outbox ORDER BY id ASC")
    statuses = [row["published"] for row in cur.fetchall()]
    assert statuses == [1, 1]

    # Relay again yields 0 rows
    assert relay.relay_once(max_rows=10) == 0

    conn.close()


def _outbox_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, run_id TEXT NOT NULL, "
        "payload TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0, created_at TEXT)"
    )
    return conn


def _event(event_id: str, **payload: Any) -> str:
    return json.dumps(
        {
            "event_id": event_id,
            "run_id": "run-1",
            "seq": 0,
            "ts": "2026-11-08T12:00:00Z",
            "actor": {"kind": "service", "role": "system", "name": "S"},
            "kind": "state_changed",
            "correlation_id": "c",
            "payload": payload,
        }
    )


def test_relay_hands_the_log_validated_envelopes_with_nested_payloads() -> None:
    conn = _outbox_conn()
    conn.execute("INSERT INTO outbox (event_id, run_id, payload) VALUES (?, ?, ?)", ("e1", "run-1", _event("e1", nested={"a": [1, 2]})))
    conn.commit()
    seen: list[Any] = []

    class Log:
        def append(self, events: list[Any]) -> list[int]:
            seen.extend(events)
            return [1]

    OutboxRelay(store=SimpleNamespace(conn=conn), log=Log()).relay_once()  # type: ignore[arg-type]
    assert seen[0].kind.value == "state_changed"
    assert seen[0].payload == {"nested": {"a": [1, 2]}}
    assert isinstance(seen[0].payload, dict)


def test_one_invalid_row_is_quarantined_and_does_not_block_the_rest() -> None:
    conn = _outbox_conn()
    conn.execute("INSERT INTO outbox (event_id, run_id, payload) VALUES (?, ?, ?)", ("bad", "run-1", '{"event_id": "bad"}'))
    conn.execute("INSERT INTO outbox (event_id, run_id, payload) VALUES (?, ?, ?)", ("good", "run-1", _event("good")))
    conn.commit()
    appended: list[str] = []

    class Log:
        def append(self, events: list[Any]) -> list[int]:
            appended.extend(str(e.event_id) for e in events)
            return list(range(len(events)))

    relay = OutboxRelay(store=SimpleNamespace(conn=conn), log=Log())  # type: ignore[arg-type]
    assert relay.relay_once() == 1
    assert appended == ["good"]
    states = {r["event_id"]: r["published"] for r in conn.execute("SELECT event_id, published FROM outbox")}
    assert states == {"bad": -1, "good": 1}
    assert relay.relay_once() == 0  # the quarantined row is not retried


def test_rows_stay_pending_when_the_log_append_fails() -> None:
    conn = _outbox_conn()
    conn.execute("INSERT INTO outbox (event_id, run_id, payload) VALUES (?, ?, ?)", ("e1", "run-1", _event("e1")))
    conn.commit()

    class Log:
        def append(self, events: list[Any]) -> list[int]:
            raise RuntimeError("disk full")

    with pytest.raises(RuntimeError):
        OutboxRelay(store=SimpleNamespace(conn=conn), log=Log()).relay_once()  # type: ignore[arg-type]
    assert conn.execute("SELECT published FROM outbox").fetchone()["published"] == 0


def test_relay_respects_max_rows_and_commit_order() -> None:
    conn = _outbox_conn()
    for i in range(5):
        conn.execute("INSERT INTO outbox (event_id, run_id, payload) VALUES (?, ?, ?)", (f"e{i}", "run-1", _event(f"e{i}")))
    conn.commit()
    order: list[str] = []

    class Log:
        def append(self, events: list[Any]) -> list[int]:
            order.extend(str(e.event_id) for e in events)
            return list(range(len(events)))

    relay = OutboxRelay(store=SimpleNamespace(conn=conn), log=Log())  # type: ignore[arg-type]
    assert relay.relay_once(max_rows=2) == 2
    assert relay.relay_once(max_rows=10) == 3
    assert order == ["e0", "e1", "e2", "e3", "e4"]
