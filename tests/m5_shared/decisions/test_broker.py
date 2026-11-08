# FILE: tests/m5_shared/decisions/test_broker.py
# ROLE: Tests that prove src/asf/m5_shared/decisions/broker.py meets its DONE WHEN conditions.
# ARCH REF: M5; p10 Decision Broker; p02 Decision Inbox; IF-03; IF-04; D-10; D-21; D-22; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/decisions/broker.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/decisions/test_broker.py` on Windows and Linux once src/asf/m5_shared/decisions/broker.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/decisions/test_broker.py` and `uv run mypy tests/m5_shared/decisions/test_broker.py` are clean.

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from asf.m5_shared.decisions.broker import DecisionBroker


def _create_decisions_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS decisions (
            decision_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            task_id TEXT,
            topic TEXT NOT NULL,
            status TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            payload TEXT NOT NULL DEFAULT '{}',
            created_at TEXT
        );
        """
    )
    conn.commit()


def test_decision_broker_meets_contract(tmp_path: Path) -> None:
    """Prove DecisionBroker behaves as declared in src/asf/m5_shared/decisions/broker.py."""
    db_file = tmp_path / "decisions.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    _create_decisions_table(conn)

    store = SimpleNamespace(conn=conn)
    broker = DecisionBroker(store=store)  # type: ignore[arg-type]

    now = datetime.now(UTC)

    # 1. Decision request that allows safe default
    req_auto = SimpleNamespace(
        decision_id="dec-1",
        run_id="run-1",
        task_id="task-1",
        kind=SimpleNamespace(value="clarify"),
        requester="m2_request/understanding",
        question="Should we support Python 3.14?",
        options=["yes", "no"],
        default_on_timeout="yes",
        deadline=now - timedelta(seconds=10),  # expired
        evidence_refs=[],
        model_dump_json=lambda: (
            '{"decision_id": "dec-1", "run_id": "run-1", "task_id": "task-1", "kind": "clarify", '
            '"requester": "m2_request/understanding", "question": "Should we support Python 3.14?", '
            '"options": ["yes", "no"], "default_on_timeout": "yes", '
            f'"deadline": "{(now - timedelta(seconds=10)).isoformat()}", "evidence_refs": []}}'
        ),
        model_dump=lambda: {"decision_id": "dec-1", "question": "Should we support Python 3.14?"},
    )

    # 2. Decision request that is in NEVER_AUTO_APPROVED
    req_never = SimpleNamespace(
        decision_id="dec-2",
        run_id="run-1",
        task_id="task-1",
        kind=SimpleNamespace(value="breaking_contract"),
        requester="m4_execution/worker",
        question="Allow breaking contract?",
        options=["approve", "reject"],
        default_on_timeout="reject",
        deadline=now - timedelta(seconds=10),  # expired, but NEVER_AUTO_APPROVED
        evidence_refs=[],
        model_dump_json=lambda: (
            '{"decision_id": "dec-2", "run_id": "run-1", "task_id": "task-1", "kind": "breaking_contract", '
            '"requester": "m4_execution/worker", "question": "Allow breaking contract?", '
            '"options": ["approve", "reject"], "default_on_timeout": "reject", '
            f'"deadline": "{(now - timedelta(seconds=10)).isoformat()}", "evidence_refs": []}}'
        ),
        model_dump=lambda: {"decision_id": "dec-2", "question": "Allow breaking contract?"},
    )

    broker.request(req_auto)  # type: ignore[arg-type]
    broker.request(req_never)  # type: ignore[arg-type]

    # Verify pending
    pending_all = broker.pending()
    assert len(pending_all) == 2
    assert {p.decision_id for p in pending_all} == {"dec-1", "dec-2"}

    pending_run = broker.pending(run_id="run-1")
    assert len(pending_run) == 2

    pending_other = broker.pending(run_id="run-99")
    assert len(pending_other) == 0

    # Sweep deadlines: dec-1 should auto-resolve, dec-2 should stay pending!
    applied = broker.sweep_deadlines()
    assert len(applied) == 1
    assert applied[0].decision_id == "dec-1"
    assert applied[0].choice == "yes"
    assert applied[0].applied_default is True

    # Check pending again: only dec-2 remains
    pending_after = broker.pending()
    assert len(pending_after) == 1
    assert pending_after[0].decision_id == "dec-2"

    # Resolve dec-2 explicitly with invalid choice -> raises ValueError
    ans_invalid = SimpleNamespace(
        decision_id="dec-2",
        choice="maybe",
        text=None,
        answered_by="user",
        answered_at=now,
        applied_default=False,
        model_dump=lambda **kwargs: {"decision_id": "dec-2", "choice": "maybe"},
    )
    with pytest.raises(ValueError, match="Invalid choice"):
        broker.resolve(ans_invalid)  # type: ignore[arg-type]

    # Resolve dec-2 with valid choice
    ans_valid = SimpleNamespace(
        decision_id="dec-2",
        choice="reject",
        text="Rejected contract break",
        answered_by="user",
        answered_at=now,
        applied_default=False,
        model_dump=lambda **kwargs: {"decision_id": "dec-2", "choice": "reject"},
    )
    broker.resolve(ans_valid)  # type: ignore[arg-type]

    # No pending decisions remaining
    assert len(broker.pending()) == 0

    conn.close()
