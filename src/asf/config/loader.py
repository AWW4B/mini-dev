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

import importlib.resources
import os
import tomllib
from pathlib import Path
from typing import Any

import tomlkit

from asf.config.paths import AppPaths, get_paths

_DEFAULTS_PACKAGE = "asf.config.defaults"


def _read_toml_bytes(data: bytes) -> dict[str, Any]:
    return tomllib.loads(data.decode("utf-8"))


def _read_toml_file(path: Path) -> dict[str, Any]:
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into a copy of *base*."""
    result: dict[str, Any] = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)  # type: ignore[arg-type]
        else:
            result[key] = value
    return result


_API_KEY_SUFFIXES = ("_api_key", "_token", "_secret")


def _env_overrides() -> dict[str, Any]:
    """Read FACTORY_<KEY> (single-part) and FACTORY_<SECTION>_<KEY> env vars.

    API-key shaped variables (ending in _API_KEY / _TOKEN / _SECRET) are
    skipped so they never leak into config dicts or logs.
    """
    prefix = "FACTORY_"
    result: dict[str, Any] = {}
    for env_key, env_val in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        rest = env_key[len(prefix):]
        rest_lower = rest.lower()
        # Skip secrets
        if any(rest_lower.endswith(s) for s in _API_KEY_SUFFIXES):
            continue
        parts = rest_lower.split("_", 1)
        if len(parts) == 2:
            section, key = parts
            if section not in result:
                result[section] = {}
            if isinstance(result[section], dict):
                result[section][key] = env_val  # type: ignore[index]
        else:
            result[parts[0]] = env_val
    return result


def load_layered(name: str, project_root: Path | None = None, cli_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge <name>.toml across all layers and return a plain dict.

    Layer order (last wins):
    1. Package defaults  (asf/config/defaults/<name>.toml)
    2. User config dir   (<config_dir>/<name>.toml)
    3. Project .factory  (<project_root>/.factory/<name>.toml)
    4. FACTORY_* env vars
    5. cli_overrides
    """
    merged: dict[str, Any] = {}

    # Layer 1: package defaults
    try:
        pkg_ref = importlib.resources.files(_DEFAULTS_PACKAGE).joinpath(f"{name}.toml")
        raw = pkg_ref.read_bytes()
        merged = _deep_merge(merged, _read_toml_bytes(raw))
    except (FileNotFoundError, TypeError, AttributeError):
        pass

    # Layer 2: user config dir
    paths: AppPaths = get_paths()
    user_toml = paths.config_dir / f"{name}.toml"
    if user_toml.is_file():
        merged = _deep_merge(merged, _read_toml_file(user_toml))

    # Layer 3: project .factory dir
    if project_root is not None:
        project_toml = project_root / ".factory" / f"{name}.toml"
        if project_toml.is_file():
            merged = _deep_merge(merged, _read_toml_file(project_toml))

    # Layer 4: env overrides
    merged = _deep_merge(merged, _env_overrides(name))

    # Layer 5: CLI overrides
    if cli_overrides:
        merged = _deep_merge(merged, cli_overrides)

    return merged


def write_user_toml(name: str, data: dict[str, Any]) -> Path:
    """Write (or overwrite) <config_dir>/<name>.toml using tomlkit (preserves comments on subsequent edits)."""
    paths = get_paths()
    dest = paths.config_dir / f"{name}.toml"
    dest.parent.mkdir(parents=True, exist_ok=True)

    # If file exists, load existing doc and merge to preserve comments
    if dest.is_file():
        with open(dest, encoding="utf-8") as fh:
            doc = tomlkit.load(fh)
    else:
        doc = tomlkit.document()

    for key, value in data.items():
        doc[key] = value  # type: ignore[index]

    with open(dest, "w", encoding="utf-8") as fh:
        tomlkit.dump(doc, fh)

    return dest
