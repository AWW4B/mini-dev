# FILE: tests/m5_shared/state_store/test_schema.py
# ROLE: Tests that prove src/asf/m5_shared/state_store/schema.py meets its DONE WHEN conditions.
# ARCH REF: M5; p09; D-05; D-23; D-24; D-32; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/state_store/schema.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/state_store/schema.py: migrate, SCHEMA_VERSION (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/state_store/test_schema.py` on Windows and Linux once src/asf/m5_shared/state_store/schema.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/state_store/test_schema.py` and `uv run mypy tests/m5_shared/state_store/test_schema.py` are clean.

import sqlite3
from pathlib import Path

from asf.m5_shared.state_store.schema import SCHEMA_VERSION, migrate


def test_migrate_meets_contract(tmp_path: Path) -> None:
    """Prove migrate behaves as declared in src/asf/m5_shared/state_store/schema.py."""
    db_file = tmp_path / "test_state.db"
    conn = sqlite3.connect(str(db_file))

    # Initial migration
    migrate(conn)

    # Check foreign keys pragma
    fk_cur = conn.execute("PRAGMA foreign_keys;")
    fk_row = fk_cur.fetchone()
    assert fk_row is not None and fk_row[0] == 1

    # Check expected tables
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cur.fetchall()}
    expected_tables = {
        "meta",
        "runs",
        "tasks",
        "attempts",
        "leases",
        "commands",
        "decisions",
        "events",
        "outbox",
        "call_metrics",
        "tool_metrics",
        "limit_events",
        "contracts",
        "memory",
    }
    assert expected_tables.issubset(tables)

    # Check meta table records SCHEMA_VERSION
    cur = conn.execute("SELECT value FROM meta WHERE key = 'schema_version';")
    meta_row = cur.fetchone()
    assert meta_row is not None
    assert int(meta_row[0]) == SCHEMA_VERSION

    # Idempotent re-run
    migrate(conn)

    conn.close()


def test_s_c_h_e_m_a__v_e_r_s_i_o_n_meets_contract() -> None:
    """Prove SCHEMA_VERSION behaves as declared in src/asf/m5_shared/state_store/schema.py."""
    assert isinstance(SCHEMA_VERSION, int)
    assert SCHEMA_VERSION >= 1


def test_migrate_really_enables_wal_normal_sync_and_foreign_keys(tmp_path: Path) -> None:
    conn = sqlite3.connect(str(tmp_path / "state.db"), autocommit=False)
    migrate(conn)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1  # NORMAL
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.close()
