# FILE: src/asf/config/loader.py
# ROLE: Loads TOML config files in layers: package defaults -> user dir -> project .factory -> FACTORY_* env -> CLI overrides.
# ARCH REF: D-37
# OWNS: Layer merge and TOML read/write (tomllib / tomlkit)
# DOES NOT OWN: Validation (settings.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/paths.py: AppPaths, get_paths (cross-platform base directories)
#   - called by src/asf/m5_shared/metrics/pricing.py: load_layered
#   - called by src/asf/m5_shared/tools/policy.py: load_layered
#   - called by src/asf/m5_shared/tools/mcp_client.py: load_layered
#   - called by src/asf/config/settings.py: load_layered
#   - called by src/asf/m2_request/repository_intake.py: load_layered
#   - called by src/asf/cli/commands/init.py: write_user_toml
#   - called by src/asf/cli/commands/models.py: write_user_toml
#   - called by tests/config/test_loader.py: load_layered, write_user_toml
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Read with tomllib; write (models init, config edits) with tomlkit to preserve comments.
#   9. Package defaults are read with importlib.resources from asf.config.defaults.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/config/test_loader.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/config/loader.py` and `uv run mypy src/asf/config/loader.py` are clean.

from pathlib import Path
from typing import Any


def load_layered(name: str, project_root: Path | None = None, cli_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge <name>.toml across all layers and return a plain dict."""
    raise NotImplementedError


def write_user_toml(name: str, data: dict[str, Any]) -> Path:
    raise NotImplementedError
