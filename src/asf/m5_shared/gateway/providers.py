# FILE: src/asf/m5_shared/gateway/providers.py
# ROLE: Builds LangChain chat models for a route: local OpenAI-compatible, OpenAI, Groq, xAI, Gemini, Anthropic.
# ARCH REF: M5; p11; D-07; D-08; D-09
# OWNS: Route config and chat-model construction
# DOES NOT OWN: Budgets, fallbacks and retries (gateway.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/secrets.py: get_api_key (D-38 keys)
#   - called by src/asf/m5_shared/gateway/gateway.py: RouteConfig, build_chat_model
#   - called by tests/m5_shared/gateway/test_providers.py: RouteConfig, build_chat_model
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Prefer ChatOpenAI with base_url for OpenAI-compatible providers (local servers, Groq, xAI, OpenAI, Gemini compatibility endpoint); use langchain-anthropic / langchain-google-genai only when installed as extras.
#   6. Never log or embed the API key; pass it only to the client constructor.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; hardcoded model names (models come from models.toml)
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/gateway/test_providers.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/gateway/providers.py` and `uv run mypy src/asf/m5_shared/gateway/providers.py` are clean.

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, SecretStr

from asf.config.secrets import get_api_key

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


class RouteConfig(BaseModel):
    provider: str
    model: str
    base_url: str | None = None
    params: dict[str, object] = {}
    reasoning_effort: str | None = None


def build_chat_model(route: RouteConfig) -> "BaseChatModel":
    from langchain_openai import ChatOpenAI  # imported when a model is built: it costs seconds and most commands never build one

    provider = route.provider.lower().strip()
    key = get_api_key(route.provider)
    if provider == "gemini" and not key:
        key = get_api_key("google")
    elif provider == "google" and not key:
        key = get_api_key("gemini")

    if provider in ("local", "llama", "llama-server", "ollama", "vllm"):
        local_base_url = route.base_url or "http://127.0.0.1:8080/v1"
        api_key = SecretStr(key or "local")
        extra: dict[str, Any] = dict(route.params)
        if route.reasoning_effort:
            extra["reasoning_effort"] = route.reasoning_effort
        return ChatOpenAI(model=route.model, api_key=api_key, base_url=local_base_url, **extra)

    # For external providers, key is required
    if not key:
        raise ValueError(
            f"Missing API key for provider '{route.provider}'. Set FACTORY_{route.provider.upper()}_API_KEY or configure keyring."
        )

    secret_key = SecretStr(key)

    if provider in ("anthropic", "claude"):
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as err:
            raise RuntimeError("langchain-anthropic is not installed. Install with extra 'anthropic'.") from err
        anthropic_extra: dict[str, Any] = dict(route.params)
        if route.base_url:
            anthropic_extra["base_url"] = route.base_url
        return ChatAnthropic(model_name=route.model, api_key=secret_key, **anthropic_extra)

    if provider in ("gemini", "google") and not route.base_url:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            google_extra: dict[str, Any] = dict(route.params)
            return ChatGoogleGenerativeAI(model=route.model, google_api_key=secret_key, **google_extra)
        except ImportError:
            pass

    # OpenAI, Groq, xAI, or Gemini compatibility endpoint via ChatOpenAI
    openai_extra: dict[str, Any] = dict(route.params)
    if route.reasoning_effort:
        openai_extra["reasoning_effort"] = route.reasoning_effort

    base_url: str | None = route.base_url
    if not base_url:
        if provider == "groq":
            base_url = "https://api.groq.com/openai/v1"
        elif provider == "xai":
            base_url = "https://api.x.ai/v1"
        elif provider in ("gemini", "google"):
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"

    if base_url:
        return ChatOpenAI(model=route.model, api_key=secret_key, base_url=base_url, **openai_extra)
    return ChatOpenAI(model=route.model, api_key=secret_key, **openai_extra)
