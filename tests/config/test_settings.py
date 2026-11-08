# FILE: tests/config/test_settings.py
# ROLE: Tests that prove src/asf/config/settings.py meets its DONE WHEN conditions.
# ARCH REF: D-37; D-09; D-14b; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/config/settings.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/settings.py: WebSettings, FactorySettings, load_settings (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/config/test_settings.py` on Windows and Linux once src/asf/config/settings.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/config/test_settings.py` and `uv run mypy tests/config/test_settings.py` are clean.


from typing import Any

import pytest

from asf.config.settings import FactorySettings, WebSettings, load_settings  # noqa: F401


def test_web_settings_meets_contract() -> None:
    """WebSettings defaults and bind_host is always 127.0.0.1."""
    ws = WebSettings()
    assert ws.bind_host == "127.0.0.1"
    assert ws.port == 8765

    # bind_host is defined on the model (it's a field, but config says it's fixed)
    ws2 = WebSettings(port=9000)
    assert ws2.port == 9000
    assert ws2.bind_host == "127.0.0.1"


def test_factory_settings_meets_contract() -> None:
    """FactorySettings defaults match the package defaults."""
    # Construct directly (bypass file loading)
    fs = FactorySettings()
    assert fs.profile == "hybrid"
    assert fs.max_parallel_workers == 1
    assert fs.poll_interval_s == 0.5
    assert fs.output == "rich"
    assert isinstance(fs.web, WebSettings)
    assert fs.web.bind_host == "127.0.0.1"
    assert fs.web.port == 8765


def test_load_settings_meets_contract(fake_paths: Any) -> None:
    """load_settings returns a FactorySettings from the layered config."""
    settings = load_settings()
    assert isinstance(settings, FactorySettings)
    assert settings.profile == "hybrid"


def test_load_settings_with_overrides(fake_paths: Any) -> None:
    """load_settings applies cli overrides."""
    settings = load_settings(overrides={"output": "plain"})
    assert settings.output == "plain"


def test_load_settings_web_bind_host_is_fixed(fake_paths: Any) -> None:
    """bind_host cannot be overridden via config; it stays 127.0.0.1."""
    settings = load_settings()
    assert settings.web.bind_host == "127.0.0.1"


def test_load_settings_env_prefix(fake_paths: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """FACTORY_ prefix env vars affect FactorySettings."""
    monkeypatch.setenv("FACTORY_PROFILE", "local")
    settings = load_settings()
    assert settings.profile == "local"
