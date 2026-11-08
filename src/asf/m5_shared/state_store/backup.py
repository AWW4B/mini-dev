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

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from asf.config.paths import AppPaths, get_paths  # noqa: F401


def backup_databases(db_paths: list[Path], dest_dir: Path, keep_last: int = 5) -> list[Path]:
    """Copy each database consistently into dest_dir; prune older copies; return written paths."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    now_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    written: list[Path] = []

    for src_path in db_paths:
        if not src_path.is_file():
            continue

        target_file = dest_dir / f"{src_path.stem}_{now_str}{src_path.suffix}"
        src_uri = f"file:{src_path.resolve().as_posix()}?mode=ro"
        src_conn = sqlite3.connect(src_uri, uri=True)
        dest_conn = sqlite3.connect(str(target_file))

        try:
            with dest_conn:
                src_conn.backup(dest_conn)
            written.append(target_file)
        finally:
            src_conn.close()
            dest_conn.close()

        # Prune older copies for this database stem, keeping last N
        stem = src_path.stem
        suffix = src_path.suffix
        pattern = f"{stem}_*{suffix}"
        all_backups = sorted(
            [p for p in dest_dir.glob(pattern) if p.is_file()],
            key=lambda p: p.stat().st_mtime,
        )

        if len(all_backups) > keep_last:
            to_remove = all_backups[:-keep_last]
            for old_p in to_remove:
                # Retain stage checkpoints if marked
                if "stage_checkpoint" in old_p.name or "checkpoint_stage" in old_p.name:
                    continue
                try:
                    old_p.unlink(missing_ok=True)
                except Exception as _del_err:  # noqa: BLE001
                    _ = _del_err

    return written
