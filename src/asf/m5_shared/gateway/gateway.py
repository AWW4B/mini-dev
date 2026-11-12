# FILE: src/asf/m5_shared/gateway/gateway.py
# ROLE: The only door for model calls: returns wrapped LangChain Runnables per role with budget checks, fallbacks, retries, schema enforcement and usage callbacks.
# ARCH REF: M5; p11 Model Gateway; IF-12 InferenceRequest; D-07; D-09; D-10; A-4
# OWNS: Role->route resolution, fallback chains, budget gate, retry policy
# DOES NOT OWN: Prompt content (agents); local process management (runtime)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/models.py: ModelRole (roles)
#   - imports from src/asf/contracts/budget.py: RunBudget (limits)
#   - imports from src/asf/m5_shared/gateway/providers.py: RouteConfig, build_chat_model (construction)
#   - imports from src/asf/m5_shared/gateway/usage_callback.py: UsageCallbackHandler (accounting)
#   - imports from src/asf/contracts/errors.py: BudgetExceeded, ProviderUnavailable (error types)
#   - called by src/asf/m5_shared/context/compaction.py: ModelGateway
#   - called by src/asf/m2_request/prompt_normalisation.py: ModelGateway
#   - called by src/asf/m2_request/request_understanding.py: ModelGateway
#   - called by src/asf/m3_orchestration/planning/strategies.py: ModelGateway
#   - called by src/asf/m3_orchestration/planning/test_authoring.py: ModelGateway
#   - called by src/asf/m3_orchestration/decomposition/rubric.py: ModelGateway
#   - called by src/asf/m3_orchestration/decomposition/splitter.py: ModelGateway
#   - called by src/asf/m4_execution/worker/strategies.py: ModelGateway
#   - called by src/asf/m4_execution/verification/failure_classifier.py: ModelGateway
#   - called by src/asf/m4_execution/verification/reviewer.py: ModelGateway
#   - called by src/asf/cli/commands/models.py: ModelGateway
#   - called by tests/m5_shared/gateway/test_gateway.py: ModelGateway
#   - called by src/asf/m4_execution/worker/worker_graph.py: ModelGateway
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Fallback chain order comes from the active profile in models.toml; T3 falls back to the second API provider before degraded mode (D-10).
#   6. Retries: at most 3, exponential backoff with jitter, honour Retry-After; non-retryable 4xx fail fast.
#   7. Structured output via with_structured_output(method="json_schema"); at most 2 re-asks on invalid output.
#   8. Refuse role T1 for purpose "acceptance_tests" (A-4).
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; direct HTTP calls (go through LangChain models); network inside the sandbox
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/gateway/test_gateway.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/gateway/gateway.py` and `uv run mypy src/asf/m5_shared/gateway/gateway.py` are clean.

import logging
import tomllib
from pathlib import Path
from typing import Any

from langchain_core.runnables import Runnable

from asf.contracts.budget import RunBudget
from asf.contracts.errors import BudgetExceeded, ProviderUnavailable
from asf.contracts.models import ModelRole
from asf.m5_shared.gateway.providers import RouteConfig, build_chat_model
from asf.m5_shared.gateway.usage_callback import UsageCallbackHandler

logger = logging.getLogger(__name__)


class ModelGateway:
    profile_name: str
    budget: RunBudget
    roles: dict[str, dict[str, Any]]
    strategies: dict[str, str]

    def __init__(self, profile_name: str, budget: RunBudget) -> None:
        self.profile_name = profile_name
        self.budget = budget
        self.roles = {}
        self.strategies = {}
        self._load_config()

    def _load_config(self) -> None:
        cfg_path = Path(__file__).resolve().parents[2] / "config" / "defaults" / "models.toml"
        data: dict[str, Any] = {}
        if cfg_path.is_file():
            try:
                with open(cfg_path, "rb") as fh:
                    data = tomllib.load(fh)
            except (OSError, tomllib.TOMLDecodeError):
                logger.warning("could not read the model profile file %s; using the built-in profile", cfg_path, exc_info=True)
                data = {}

        profiles = data.get("profiles", {})
        profile_data = profiles.get(self.profile_name, {})
        self.roles = profile_data.get("roles", {})
        self.strategies = data.get("strategies", {})

        if not self.roles:
            if self.profile_name == "local-only":
                self.roles = {
                    "T1": {"provider": "local", "model": ""},
                    "T2": {"provider": "local", "model": ""},
                    "T3": {"provider": "local", "model": ""},
                    "reviewer": {"provider": "local", "model": ""},
                }
            elif self.profile_name == "api-heavy":
                self.roles = {
                    "T1": {"provider": "groq", "model": ""},
                    "T2": {"provider": "openai", "model": ""},
                    "T3": {"provider": "anthropic", "model": "", "fallbacks": ["openai"]},
                    "reviewer": {"provider": "gemini", "model": ""},
                }
            else:  # hybrid
                self.roles = {
                    "T1": {"provider": "local", "model": ""},
                    "T2": {"provider": "local", "model": ""},
                    "T3": {"provider": "openai", "model": "", "fallbacks": ["groq"]},
                    "reviewer": {"provider": "openai", "model": ""},
                }

    def baseline_warnings(self) -> list[str]:
        """D-09: warn (never block) when the profile lacks 2 API providers, a local coder or the tiny model."""
        warnings: list[str] = []
        providers_used: set[str] = set()
        has_local_coder = False
        has_tiny_model = False

        for role_name, rdata in self.roles.items():
            prov = str(rdata.get("provider", ""))
            if prov and prov != "local":
                providers_used.add(prov)
            for fb in rdata.get("fallbacks", []):
                fb_str = str(fb)
                if fb_str and fb_str != "local":
                    providers_used.add(fb_str)
            if role_name in ("T2", "coder") and prov == "local":
                has_local_coder = True
            if role_name in ("T1", "tiny") and (prov == "local" or rdata.get("model", "")):
                has_tiny_model = True

        if len(providers_used) < 2:
            warnings.append("Profile lacks 2 API providers (D-09)")
        if not has_local_coder:
            warnings.append("Profile lacks a local coder (D-09)")
        if not has_tiny_model:
            warnings.append("Profile lacks the tiny model (D-09)")

        return warnings

    def model_for(
        self,
        role: ModelRole,
        purpose: str,
        output_schema: type[Any] | None = None,
        task_id: str | None = None,
    ) -> Runnable[Any, Any]:
        role_key = role.value if hasattr(role, "value") else str(role)

        if role_key == "T1" and purpose == "acceptance_tests":
            raise ValueError("Refusing role T1 for purpose 'acceptance_tests' (A-4)")

        if self.budget.used_api_spend >= self.budget.max_api_spend:
            raise BudgetExceeded(
                f"Budget exceeded: API spend limit reached ({self.budget.used_api_spend:.2f} >= {self.budget.max_api_spend:.2f})"
            )
        if self.budget.used_remote_tokens >= self.budget.max_remote_tokens:
            raise BudgetExceeded(
                f"Budget exceeded: Remote token limit reached ({self.budget.used_remote_tokens} >= {self.budget.max_remote_tokens})"
            )

        role_cfg = self.roles.get(role_key, {})
        provider = str(role_cfg.get("provider", "local"))
        model_name = str(role_cfg.get("model", "")) or ("gpt-4o" if provider == "openai" else "default")
        fallbacks = list(role_cfg.get("fallbacks", []))

        route = RouteConfig(provider=provider, model=model_name)
        try:
            base_model = build_chat_model(route)
        except Exception as err:
            raise ProviderUnavailable(f"Provider '{provider}' unavailable: {err}") from err

        strategy = self.strategies.get("worker", "tool_loop")
        usage_handler = UsageCallbackHandler(
            run_id=str(self.budget.run_id),
            task_id=task_id,
            role=role_key,
            strategy=strategy,
        )

        runnable: Runnable[Any, Any] = base_model.with_retry(stop_after_attempt=3)

        if output_schema is not None:
            structured = getattr(base_model, "with_structured_output", None)
            if structured is not None:
                try:
                    runnable = base_model.with_structured_output(output_schema, method="json_schema").with_retry(
                        stop_after_attempt=3
                    )
                except Exception:  # noqa: BLE001 - the provider rejects strict json_schema output: use its default mode
                    logger.debug("json_schema structured output unsupported by %s; using the default method", provider, exc_info=True)
                    runnable = base_model.with_structured_output(output_schema).with_retry(stop_after_attempt=3)

        if fallbacks:
            fallback_models: list[Runnable[Any, Any]] = []
            for fb_provider in fallbacks:
                fb_route = RouteConfig(provider=str(fb_provider), model="default")
                try:
                    fb_chat = build_chat_model(fb_route)
                    if output_schema is not None and hasattr(fb_chat, "with_structured_output"):
                        fb_runnable = fb_chat.with_structured_output(output_schema).with_retry(stop_after_attempt=3)
                    else:
                        fb_runnable = fb_chat.with_retry(stop_after_attempt=3)
                    fallback_models.append(fb_runnable)
                except Exception:  # noqa: BLE001 - one unusable fallback route must not break the primary route
                    logger.warning("fallback route %s is unavailable and was skipped", fb_provider, exc_info=True)
            if fallback_models:
                runnable = runnable.with_fallbacks(fallback_models)

        runnable = runnable.with_config(callbacks=[usage_handler])
        return runnable
