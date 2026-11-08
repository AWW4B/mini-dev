# FILE: src/asf/m5_shared/state_store/backup.py
# ROLE: Takes consistent online backups of state.db and checkpoints.db with retention.
# ARCH REF: M5; p09 checkpoint/backup
# OWNS: Backup copies and retention
# DOES NOT OWN: Restore UX (manual)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/paths.py: AppPaths, get_paths (cross-platform base directories)
#   - called by tests/m5_shared/state_store/test_backup.py: backup_databases
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Use sqlite3.Connection.backup for consistency; keep the last N plus stage checkpoints.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/state_store/test_backup.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/state_store/backup.py` and `uv run mypy src/asf/m5_shared/state_store/backup.py` are clean.

from pathlib import Path


def backup_databases(db_paths: list[Path], dest_dir: Path, keep_last: int = 5) -> list[Path]:
    """Copy each database consistently into dest_dir; prune older copies; return written paths."""
    raise NotImplementedError
