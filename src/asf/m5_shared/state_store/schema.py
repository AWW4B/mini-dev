# FILE: src/asf/m5_shared/state_store/schema.py
# ROLE: Owns the SQLite schema of state.db and its forward-only migrations.
# ARCH REF: M5; p09; D-05; D-23; D-24; D-32
# OWNS: Table definitions (runs, tasks, attempts, leases, commands, decisions, events, outbox, call_metrics, tool_metrics, limit_events, contracts, memory) and migrations
# DOES NOT OWN: Queries and business rules (store.py)
# CONNECTS TO (external boundaries only):
#   - called by src/asf/m5_shared/state_store/store.py: migrate
#   - called by tests/m5_shared/state_store/test_schema.py: migrate, SCHEMA_VERSION
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Enable WAL mode and foreign keys on every connection.
#   9. Migrations are forward-only and idempotent; record SCHEMA_VERSION in a meta table.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/state_store/test_schema.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/state_store/schema.py` and `uv run mypy src/asf/m5_shared/state_store/schema.py` are clean.

import sqlite3

SCHEMA_VERSION: int = 1


def migrate(conn: sqlite3.Connection) -> None:
    """Create or upgrade all tables of state.db to SCHEMA_VERSION inside one transaction."""
    raise NotImplementedError
