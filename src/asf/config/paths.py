# FILE: src/asf/config/paths.py
# ROLE: Resolves every base directory (config, data, logs, cache, per-project .factory) via platformdirs.
# ARCH REF: FR-4 (no hardcoded paths); D-26; D-37; D-45
# OWNS: Directory resolution
# DOES NOT OWN: File contents
# CONNECTS TO (external boundaries only):
#   - called by src/asf/m5_shared/state_store/backup.py: AppPaths, get_paths
#   - called by src/asf/m5_shared/workspace/blobs.py: AppPaths, get_paths
#   - called by src/asf/m5_shared/runtime/backends.py: AppPaths, get_paths
#   - called by src/asf/m5_shared/tools/skills.py: AppPaths, get_paths
#   - called by src/asf/config/loader.py: AppPaths, get_paths
#   - called by src/asf/config/secrets.py: AppPaths, get_paths
#   - called by src/asf/doctor/checks.py: AppPaths, get_paths
#   - called by src/asf/doctor/report.py: AppPaths, get_paths
#   - called by src/asf/logging_setup.py: AppPaths, get_paths
#   - called by src/asf/cli/commands/init.py: AppPaths, get_paths
#   - called by tests/conftest.py: AppPaths
#   - called by tests/config/test_paths.py: AppPaths, get_paths
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Use platformdirs with appname "ai-software-factory"; honour FACTORY_HOME when set (tests and portable installs).
#   9. Create directories lazily with parents=True, exist_ok=True.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/config/test_paths.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/config/paths.py` and `uv run mypy src/asf/config/paths.py` are clean.

from pathlib import Path

from pydantic import BaseModel


class AppPaths(BaseModel):
    config_dir: Path
    data_dir: Path
    log_dir: Path
    cache_dir: Path

    def project_dir(self, project_root: Path) -> Path:
        """Return <project_root>/.factory."""
        raise NotImplementedError

    def state_db(self, project_root: Path) -> Path:
        raise NotImplementedError

    def checkpoints_db(self, project_root: Path) -> Path:
        raise NotImplementedError


def get_paths() -> AppPaths:
    raise NotImplementedError
