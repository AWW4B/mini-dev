# FILE: tests/m5_shared/events/test_event_log.py
# ROLE: Tests that prove src/asf/m5_shared/events/event_log.py meets its DONE WHEN conditions.
# ARCH REF: M5; p10 Event Stream; IF-17 EventPublish; IF-18 EventSubscribe; D-23; D-14b; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/events/event_log.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/events/event_log.py: EventLog (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/events/test_event_log.py` on Windows and Linux once src/asf/m5_shared/events/event_log.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/events/test_event_log.py` and `uv run mypy tests/m5_shared/events/test_event_log.py` are clean.

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from asf.m5_shared.events.event_log import EventLog


def _create_events_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            seq INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            kind TEXT NOT NULL,
            visibility TEXT NOT NULL,
            source TEXT NOT NULL,
            task_id TEXT,
            attempt_id TEXT,
            blob_ref TEXT,
            payload TEXT NOT NULL DEFAULT '{}',
            UNIQUE(run_id, seq)
        );
        """
    )
    conn.commit()


def test_event_log_meets_contract(tmp_path: Path) -> None:
    """Prove EventLog behaves as declared in src/asf/m5_shared/events/event_log.py."""
    db_file = tmp_path / "events.db"
    conn = sqlite3.connect(str(db_file))
    _create_events_table(conn)

    # Fake blob store
    stored_blobs: dict[str, bytes] = {}

    class FakeBlobs:
        def put(self, data: bytes) -> str:
            ref = f"sha256:fake_{len(stored_blobs)}"
            stored_blobs[ref] = data
            return ref

        def get(self, ref: str) -> bytes:
            return stored_blobs[ref]

    log = EventLog(conn=conn, blobs=FakeBlobs())  # type: ignore[arg-type]

    # Initial sequence should be 0
    assert log.latest_seq("run-1") == 0

    now = datetime.now(UTC)
    evt1 = SimpleNamespace(
        event_id="evt-1",
        run_id="run-1",
        task_id="task-1",
        seq=0,
        ts=now,
        actor=SimpleNamespace(kind="agent", role="worker", name="Worker 1", model_tier="T1"),
        kind=SimpleNamespace(value="step_started"),
        causation_id=None,
        correlation_id="corr-1",
        payload={"step": 1, "api_key": "secret_abc_123"},
        payload_ref=None,
        visibility=SimpleNamespace(value="user"),
        redacted=False,
    )
    evt2 = SimpleNamespace(
        event_id="evt-2",
        run_id="run-1",
        task_id="task-1",
        seq=0,
        ts=now,
        actor=SimpleNamespace(kind="service", role="system", name="Supervisor", model_tier=None),
        kind=SimpleNamespace(value="run_completed"),
        causation_id=None,
        correlation_id="corr-1",
        payload={"status": "success"},
        payload_ref=None,
        visibility=SimpleNamespace(value="internal"),
        redacted=False,
    )

    # Append events
    seqs = log.append([evt1, evt2])  # type: ignore[list-item]
    assert seqs == [1, 2]
    assert log.latest_seq("run-1") == 2

    # Idempotent append of already-seen event_id returns existing seq
    seqs_dupe = log.append([evt1])  # type: ignore[list-item]
    assert seqs_dupe == [1]
    assert log.latest_seq("run-1") == 2

    # Read events
    read_all = log.read("run-1", after_seq=0)
    assert len(read_all) == 2
    assert read_all[0].event_id == "evt-1"
    assert read_all[0].seq == 1
    # Check redaction occurred
    assert read_all[0].payload["api_key"] == "[REDACTED]"
    assert read_all[1].event_id == "evt-2"
    assert read_all[1].seq == 2

    # Read with after_seq cursor
    read_cursor = log.read("run-1", after_seq=1)
    assert len(read_cursor) == 1
    assert read_cursor[0].event_id == "evt-2"

    # Read with visibility filter
    read_user = log.read("run-1", after_seq=0, visibility=SimpleNamespace(value="user"))  # type: ignore[arg-type]
    assert len(read_user) == 1
    assert read_user[0].event_id == "evt-1"

    # Large payload offload (> 8 KB)
    large_dict = {"data": "X" * 9000}
    evt3 = SimpleNamespace(
        event_id="evt-3",
        run_id="run-1",
        task_id=None,
        seq=0,
        ts=now,
        actor=SimpleNamespace(kind="agent", role="worker", name="Worker 1", model_tier="T1"),
        kind=SimpleNamespace(value="tool_result"),
        causation_id=None,
        correlation_id="corr-2",
        payload=large_dict,
        payload_ref=None,
        visibility=SimpleNamespace(value="user"),
        redacted=False,
    )
    seqs3 = log.append([evt3])  # type: ignore[list-item]
    assert seqs3 == [3]
    read_large = log.read("run-1", after_seq=2)
    assert len(read_large) == 1
    assert read_large[0].payload_ref is not None
    assert read_large[0].payload_ref.startswith("sha256:")

    conn.close()
