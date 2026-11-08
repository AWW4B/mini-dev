# FILE: tests/m5_shared/gateway/test_providers.py
# ROLE: Tests that prove src/asf/m5_shared/gateway/providers.py meets its DONE WHEN conditions.
# ARCH REF: M5; p11; D-07; D-08; D-09; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/gateway/providers.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/gateway/providers.py: RouteConfig, build_chat_model (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/gateway/test_providers.py` on Windows and Linux once src/asf/m5_shared/gateway/providers.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/gateway/test_providers.py` and `uv run mypy tests/m5_shared/gateway/test_providers.py` are clean.


import pytest
from langchain_core.language_models.chat_models import BaseChatModel

from asf.m5_shared.gateway.providers import RouteConfig, build_chat_model


def test_route_config_meets_contract() -> None:
    """Prove RouteConfig behaves as declared in src/asf/m5_shared/gateway/providers.py."""
    cfg = RouteConfig(provider="openai", model="gpt-4o")
    assert cfg.provider == "openai"
    assert cfg.model == "gpt-4o"
    assert cfg.base_url is None
    assert cfg.params == {}
    assert cfg.reasoning_effort is None

    # Serialization and custom fields
    custom = RouteConfig(
        provider="groq",
        model="llama-3.3-70b-versatile",
        base_url="https://api.groq.com/openai/v1",
        params={"temperature": 0.5},
        reasoning_effort="medium",
    )
    dumped = custom.model_dump()
    loaded = RouteConfig.model_validate(dumped)
    assert loaded == custom


def test_build_chat_model_meets_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prove build_chat_model behaves as declared in src/asf/m5_shared/gateway/providers.py."""
    # 1. Local route (does not require external API key)
    local_cfg = RouteConfig(provider="local", model="qwen2.5-coder")
    local_model = build_chat_model(local_cfg)
    assert isinstance(local_model, BaseChatModel)

    # 2. Missing API key for cloud provider raises ValueError
    monkeypatch.delenv("FACTORY_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("FACTORY_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("FACTORY_GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("FACTORY_GROQ_API_KEY", raising=False)
    monkeypatch.delenv("FACTORY_XAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="API key"):
        build_chat_model(RouteConfig(provider="openai", model="gpt-4o"))

    # 3. OpenAI route with mock key
    monkeypatch.setenv("FACTORY_OPENAI_API_KEY", "mock-openai-key")  # noqa: S106
    openai_model = build_chat_model(RouteConfig(provider="openai", model="gpt-4o"))
    assert isinstance(openai_model, BaseChatModel)

    # 4. Groq route with mock key
    monkeypatch.setenv("FACTORY_GROQ_API_KEY", "mock-groq-key")  # noqa: S106
    groq_model = build_chat_model(RouteConfig(provider="groq", model="llama-3.3-70b-versatile"))
    assert isinstance(groq_model, BaseChatModel)

    # 5. Anthropic route with mock key
    monkeypatch.setenv("FACTORY_ANTHROPIC_API_KEY", "mock-anthropic-key")  # noqa: S106
    anthropic_model = build_chat_model(RouteConfig(provider="anthropic", model="claude-3-5-sonnet-20241022"))
    assert isinstance(anthropic_model, BaseChatModel)

    # 6. Gemini route with mock key
    monkeypatch.setenv("FACTORY_GOOGLE_API_KEY", "mock-google-key")  # noqa: S106
    gemini_model = build_chat_model(RouteConfig(provider="gemini", model="gemini-1.5-pro"))
    assert isinstance(gemini_model, BaseChatModel)
