# FILE: tests/m5_shared/state_store/test_backup.py
# ROLE: Tests that prove src/asf/m5_shared/state_store/backup.py meets its DONE WHEN conditions.
# ARCH REF: M5; p09 checkpoint/backup; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/state_store/backup.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/state_store/backup.py: backup_databases (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/state_store/test_backup.py` on Windows and Linux once src/asf/m5_shared/state_store/backup.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/state_store/test_backup.py` and `uv run mypy tests/m5_shared/state_store/test_backup.py` are clean.

import sqlite3
import time
from pathlib import Path
from typing import Any

from asf.m5_shared.state_store.backup import backup_databases


def test_backup_databases_meets_contract(tmp_path: Path, fake_paths: Any) -> None:
    """Prove backup_databases behaves as declared in src/asf/m5_shared/state_store/backup.py."""
    _ = fake_paths

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    with conn:
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT);")
        conn.execute("INSERT INTO sample (id, name) VALUES (1, 'initial');")
    conn.close()

    backup_dir = tmp_path / "backups"

    # 1. First backup
    written = backup_databases([db_path], dest_dir=backup_dir, keep_last=2)
    assert len(written) == 1
    assert written[0].is_file()

    # Verify backup database contents
    b_conn = sqlite3.connect(str(written[0]))
    row = b_conn.execute("SELECT id, name FROM sample").fetchone()
    b_conn.close()
    assert row[0] == 1
    assert row[1] == "initial"

    # 2. Make additional backups to verify pruning retention (keep_last=2)
    time.sleep(0.01)
    backup_databases([db_path], dest_dir=backup_dir, keep_last=2)
    time.sleep(0.01)
    backup_databases([db_path], dest_dir=backup_dir, keep_last=2)

    remaining_backups = list(backup_dir.glob("state_*.db"))
    assert len(remaining_backups) == 2
