# FILE: tests/config/test_secrets.py
# ROLE: Tests that prove src/asf/config/secrets.py meets its DONE WHEN conditions.
# ARCH REF: D-38; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/config/secrets.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/secrets.py: get_api_key, key_sources (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/config/test_secrets.py` on Windows and Linux once src/asf/config/secrets.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/config/test_secrets.py` and `uv run mypy tests/config/test_secrets.py` are clean.


import os
from pathlib import Path

import pytest

from asf.config.paths import AppPaths
from asf.config.secrets import get_api_key, key_sources  # noqa: F401


def test_get_api_key_from_env(fake_paths: AppPaths, monkeypatch: pytest.MonkeyPatch) -> None:
    """get_api_key reads from FACTORY_<PROVIDER>_API_KEY env var."""
    monkeypatch.setenv("FACTORY_OPENAI_API_KEY", "sk-test-env-key")
    result = get_api_key("openai")
    assert result == "sk-test-env-key"


def test_get_api_key_from_dotenv(fake_paths: AppPaths, monkeypatch: pytest.MonkeyPatch) -> None:
    """get_api_key falls back to .env file in config dir."""
    monkeypatch.delenv("FACTORY_ANTHROPIC_API_KEY", raising=False)
    env_file = fake_paths.config_dir / ".env"
    env_file.write_text("FACTORY_ANTHROPIC_API_KEY=ant-test-key\n", encoding="utf-8")

    # Make sure no env var shadows it
    result = get_api_key("anthropic")
    assert result == "ant-test-key"


def test_get_api_key_missing(fake_paths: AppPaths, monkeypatch: pytest.MonkeyPatch) -> None:
    """get_api_key returns None when no key is configured."""
    monkeypatch.delenv("FACTORY_OPENAI_API_KEY", raising=False)
    result = get_api_key("openai")
    assert result is None


def test_get_api_key_meets_contract(fake_paths: AppPaths, monkeypatch: pytest.MonkeyPatch) -> None:
    """get_api_key returns str or None, never raises."""
    result = get_api_key("unknown_provider_xyz")
    assert result is None or isinstance(result, str)


def test_key_sources_meets_contract(fake_paths: AppPaths, monkeypatch: pytest.MonkeyPatch) -> None:
    """key_sources returns a dict mapping known providers to source names."""
    monkeypatch.delenv("FACTORY_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("FACTORY_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("FACTORY_GOOGLE_API_KEY", raising=False)

    sources = key_sources()
    assert isinstance(sources, dict)
    # All known providers should appear
    for provider in ("openai", "anthropic", "google"):
        assert provider in sources
        assert sources[provider] in ("keyring", "env", "dotenv", "missing")


def test_key_sources_env_provider(fake_paths: AppPaths, monkeypatch: pytest.MonkeyPatch) -> None:
    """key_sources reports 'env' when env var is set."""
    monkeypatch.setenv("FACTORY_OPENAI_API_KEY", "sk-test")
    sources = key_sources()
    assert sources.get("openai") == "env"


def test_key_sources_dotenv_provider(fake_paths: AppPaths, monkeypatch: pytest.MonkeyPatch) -> None:
    """key_sources reports 'dotenv' when key is in .env file."""
    monkeypatch.delenv("FACTORY_ANTHROPIC_API_KEY", raising=False)
    env_file = fake_paths.config_dir / ".env"
    env_file.write_text("FACTORY_ANTHROPIC_API_KEY=ant-dotenv-key\n", encoding="utf-8")

    sources = key_sources()
    assert sources.get("anthropic") == "dotenv"


def test_key_sources_reports_missing(fake_paths: AppPaths, monkeypatch: pytest.MonkeyPatch) -> None:
    """key_sources reports 'missing' for providers with no key anywhere."""
    monkeypatch.delenv("FACTORY_GOOGLE_API_KEY", raising=False)
    sources = key_sources()
    # google should be missing (no env, no dotenv set for it)
    assert sources.get("google") in ("keyring", "missing")
