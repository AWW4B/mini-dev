# FILE: src/asf/config/settings.py
# ROLE: Validated typed settings (pydantic-settings) built from the layered config.
# ARCH REF: D-37; D-09; D-14b
# OWNS: Settings models
# DOES NOT OWN: Reading files (loader.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/loader.py: load_layered (raw layers)
#   - imports from src/asf/contracts/errors.py: ConfigError (validation errors)
#   - called by src/asf/cli/commands/config_cmd.py: load_settings
#   - called by src/asf/web/server.py: load_settings
#   - called by tests/config/test_settings.py: WebSettings, FactorySettings, load_settings
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Env prefix FACTORY_; unknown keys are errors with the file and key named.
#   6. web.bind_host is fixed to "127.0.0.1" and is not configurable.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/config/test_settings.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/config/settings.py` and `uv run mypy src/asf/config/settings.py` are clean.

from pathlib import Path

from pydantic import BaseModel, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from asf.config.loader import load_layered
from asf.contracts.errors import ConfigError


class WebSettings(BaseModel):
    bind_host: str = "127.0.0.1"
    port: int = 8765


class FactorySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FACTORY_", extra="forbid")

    profile: str = "hybrid"
    max_parallel_workers: int = 1
    poll_interval_s: float = 0.5
    output: str = "rich"
    web: WebSettings = WebSettings()


_FACTORY_SETTINGS_FIELDS = frozenset(FactorySettings.model_fields.keys())


def _filter_to_known_fields(raw: dict[str, object]) -> dict[str, object]:
    """Return a copy of *raw* with only keys declared in FactorySettings (top-level)."""
    return {k: v for k, v in raw.items() if k in _FACTORY_SETTINGS_FIELDS}


def load_settings(project_root: Path | None = None, overrides: dict[str, object] | None = None) -> FactorySettings:
    """Load and validate settings from layered TOML + env, then apply any CLI overrides.

    Layer order:
    1. Package defaults + user TOML + project TOML (via load_layered without env layer)
    2. FACTORY_* env vars (handled by pydantic-settings automatically on model construction)
    3. CLI overrides
    """
    # Load only file-based layers (env handled by pydantic-settings below)
    raw = load_layered("factory", project_root=project_root)

    # web.bind_host is fixed – remove it from raw so it cannot be overridden
    if isinstance(raw.get("web"), dict):
        raw["web"].pop("bind_host", None)

    # Merge CLI overrides on top
    if overrides:
        for key, val in overrides.items():
            keys = key.split(".")
            node: dict[str, object] = raw
            for part in keys[:-1]:
                sub = node.get(part)
                if not isinstance(sub, dict):
                    sub = {}
                    node[part] = sub
                node = sub
            node[keys[-1]] = val

    # Strip env-layer artifacts that are not FactorySettings fields (e.g. FACTORY_HOME)
    cleaned = _filter_to_known_fields(raw)

    try:
        # pydantic-settings reads FACTORY_* env vars and merges with the dict
        return FactorySettings.model_validate(cleaned)
    except ValidationError as exc:
        raise ConfigError(f"Invalid factory settings: {exc}") from exc
