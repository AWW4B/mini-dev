# FILE: src/asf/config/secrets.py
# ROLE: Looks up provider API keys: keyring first, then FACTORY_<PROVIDER>_API_KEY, then a .env in the user config dir.
# ARCH REF: D-38
# OWNS: Key lookup and the key-source report for doctor
# DOES NOT OWN: Storing keys in TOML (forbidden)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/paths.py: AppPaths, get_paths (cross-platform base directories)
#   - called by src/asf/m5_shared/gateway/providers.py: get_api_key, get_api_keys
#   - called by src/asf/m5_shared/gateway/gateway.py: get_api_keys (one route per key)
#   - called by src/asf/doctor/checks.py: key_sources
#   - called by tests/config/test_secrets.py: get_api_key, key_sources
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Warn (do not fail) when the .env file is readable by other users on Linux.
#   9. Never return keys in reports; report only the source name.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; writing keys to logs, events, TOML or the sandbox environment
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/config/test_secrets.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/config/secrets.py` and `uv run mypy src/asf/config/secrets.py` are clean.

import logging
import os
import stat
import sys
from pathlib import Path

from asf.config.paths import get_paths

_LOGGER = logging.getLogger(__name__)


def _keyring_get(provider: str) -> str | None:
    """The stored key, if any. ``keyring`` is imported here because loading it costs half a second and many commands never need a key."""
    import keyring

    return keyring.get_password(_KEYRING_SERVICE, provider)

# Well-known providers that doctor checks by default
_KNOWN_PROVIDERS = ("openai", "anthropic", "google", "gemini", "groq", "xai", "openrouter", "mistral", "cerebras", "deepseek", "together")

# one provider may have several keys (free tiers are rate limited per key): FACTORY_GROQ_API_KEY, then _2, _3 ... up to this many
_MAX_KEYS = 16

_KEYRING_SERVICE = "ai-software-factory"


def _env_key_name(provider: str) -> str:
    return f"FACTORY_{provider.upper()}_API_KEY"


def _load_dotenv(config_dir: Path) -> dict[str, str]:
    """Parse a simple .env file (KEY=value lines); return a plain dict."""
    env_path = config_dir / ".env"
    if not env_path.is_file():
        return {}

    # Warn on Linux if the file is group/world-readable
    if sys.platform != "win32":
        file_stat = env_path.stat()
        if file_stat.st_mode & (stat.S_IRGRP | stat.S_IROTH):
            _LOGGER.warning(
                ".env file at %s is readable by other users; consider `chmod 600`",
                env_path,
            )

    result: dict[str, str] = {}
    with open(env_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip().strip("\"'")
    return result


def _lookup(name: str, env_name: str) -> str | None:
    """One stored value: keyring entry *name*, then the environment variable, then the .env file. Never logs it."""
    try:
        kr_val = _keyring_get(name)
        if kr_val:
            return kr_val
    except Exception as _kr_err:  # noqa: BLE001
        _LOGGER.debug("keyring unavailable for %s: %s", name, _kr_err)
    env_val = os.environ.get(env_name)
    if env_val:
        return env_val
    return _load_dotenv(get_paths().config_dir).get(env_name) or None


def get_api_keys(provider: str) -> list[str]:
    """Every key stored for *provider*, in order, without duplicates.

    The main entry may hold several keys separated by commas; further keys are FACTORY_<PROVIDER>_API_KEY_2, _3 ... (or the
    keyring entries ``<provider>_2`` ...). The numbered list ends at the first gap. Never logs a key.
    """
    keys: list[str] = []

    def add(raw: str | None) -> None:
        for part in (raw or "").split(","):
            part = part.strip()
            if part and part not in keys:
                keys.append(part)

    base = _env_key_name(provider)
    add(_lookup(provider, base))
    for n in range(2, _MAX_KEYS + 1):
        raw = _lookup(f"{provider}_{n}", f"{base}_{n}")
        if not raw:
            break
        add(raw)
    return keys


def get_api_key(provider: str) -> str | None:
    """Return the first API key for *provider*, or None if not found.

    Search order: keyring → FACTORY_<PROVIDER>_API_KEY env → .env in config dir. A comma separated value yields its first key.
    Never logs the key itself.
    """
    first = _lookup(provider, _env_key_name(provider))
    return first.split(",")[0].strip() or None if first else None


def key_sources() -> dict[str, str]:
    """Map provider -> 'keyring' | 'env' | 'dotenv' | 'missing' (never the key itself)."""
    paths = get_paths()
    dotenv = _load_dotenv(paths.config_dir)

    result: dict[str, str] = {}
    for provider in _KNOWN_PROVIDERS:
        env_name = _env_key_name(provider)

        # keyring
        try:
            kr_val = _keyring_get(provider)
            if kr_val:
                result[provider] = "keyring"
                continue
        except Exception as _kr_err:  # noqa: BLE001
            _LOGGER.debug("keyring check failed for %s: %s", provider, _kr_err)

        # env var
        if os.environ.get(env_name):
            result[provider] = "env"
            continue

        # .env file
        if dotenv.get(env_name):
            result[provider] = "dotenv"
            continue

        result[provider] = "missing"

    return result
