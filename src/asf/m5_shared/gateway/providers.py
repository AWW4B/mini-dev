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

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel


class RouteConfig(BaseModel):
    provider: str
    model: str
    base_url: str | None = None
    params: dict[str, object] = {}
    reasoning_effort: str | None = None


def build_chat_model(route: RouteConfig) -> BaseChatModel:
    raise NotImplementedError
