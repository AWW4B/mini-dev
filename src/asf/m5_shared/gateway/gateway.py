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
#   - imports from src/asf/m5_shared/trace.py: trace_event (the route chosen for every model request)
#   - imports from src/asf/config/secrets.py: get_api_keys (one route per stored key, so a rate limited key falls through to the next)
#   - imports from src/asf/config/loader.py: load_layered (the layered models.toml)
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
#   - called by src/asf/m3_orchestration/run_graph.py: ModelGateway
#   - called by src/asf/cli/commands/run.py: ModelGateway
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
from typing import TYPE_CHECKING, Any

from asf.config.loader import load_layered
from asf.config.secrets import get_api_keys
from asf.contracts.budget import RunBudget
from asf.contracts.errors import BudgetExceeded, ProviderUnavailable
from asf.contracts.models import ModelRole
from asf.m5_shared.gateway.providers import RouteConfig, build_chat_model
from asf.m5_shared.trace import trace_event

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable

logger = logging.getLogger(__name__)


class ModelGateway:
    profile_name: str
    budget: RunBudget
    roles: dict[str, dict[str, Any]]
    strategies: dict[str, str]
    providers: dict[str, dict[str, Any]]
    metrics_db: Any = None  # <project>/.factory/state.db: where model calls are recorded (call_metrics); set by the run

    def __init__(self, profile_name: str, budget: RunBudget) -> None:
        self.profile_name = profile_name
        self.budget = budget
        self.roles = {}
        self.strategies = {}
        self.providers = {}
        self._load_config()

    @staticmethod
    def default_profile_name() -> str:
        """The profile named by ``active_profile`` in models.toml: what a run uses when no --profile is given (and when it is resumed)."""
        return str(load_layered("models").get("active_profile") or "hybrid")

    def _load_config(self) -> None:
        data: dict[str, Any] = load_layered("models")  # packaged defaults, then the user's models.toml, then FACTORY_* variables

        profiles = data.get("profiles", {})
        profile_data = profiles.get(self.profile_name, {})
        self.roles = profile_data.get("roles", {})
        self.strategies = data.get("strategies", {})
        self.providers = {str(k): dict(v) for k, v in data.get("providers", {}).items()}

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
                fb_str = str(fb.get("provider", "")) if isinstance(fb, dict) else str(fb)
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
    ) -> "Runnable[Any, Any]":
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
        routes = self._routes_for(role_cfg)

        strategy = self.strategies.get("worker", "tool_loop")
        # loads langchain_core callbacks, so it is imported when a model is built, not when the module is
        from asf.m5_shared.gateway.usage_callback import UsageCallbackHandler

        usage_handler = UsageCallbackHandler(
            run_id=str(self.budget.run_id),
            task_id=task_id,
            role=role_key,
            strategy=strategy,
            budget=self.budget,
            metrics_db=self.metrics_db,
        )
        trace_event("gateway", "route", role=role_key, purpose=purpose, task=task_id, routes=[f"{r.provider}:{r.model}#{r.key_index + 1}" for r in routes], structured=getattr(output_schema, "__name__", None))

        runnables: list[Runnable[Any, Any]] = []
        first_error: Exception | None = None
        for route in routes:
            try:
                runnables.append(self._runnable(build_chat_model(route), output_schema, route.provider))
            except Exception as err:  # noqa: BLE001 - an unusable route (no key, missing extra) is skipped while another can serve
                first_error = first_error or err
                logger.warning("route %s (key %d) is unavailable and was skipped: %s", route.provider, route.key_index + 1, err)
        if not runnables:
            raise ProviderUnavailable(f"Provider '{provider}' unavailable: {first_error}") from first_error

        runnable = runnables[0].with_fallbacks(runnables[1:]) if len(runnables) > 1 else runnables[0]
        return runnable.with_config(callbacks=[usage_handler])

    def _routes_for(self, role_cfg: dict[str, Any]) -> list[RouteConfig]:
        """The ordered routes a call may take: the role's provider, then each fallback; one route per stored key.

        A fallback is a provider name or a table ``{provider, model, base_url, params}``. A name takes the model from
        ``[providers.<name>] default_model`` and the address from ``[providers.<name>] base_url``. When a provider's key
        is rate limited the next key is tried, then the next provider.
        """
        entries: list[dict[str, Any]] = [dict(role_cfg)]
        for fb in role_cfg.get("fallbacks", []):
            entries.append(dict(fb) if isinstance(fb, dict) else {"provider": str(fb)})
        routes: list[RouteConfig] = []
        for entry in entries:
            prov = str(entry.get("provider", "local"))
            table = self.providers.get(prov, {})
            model_name = str(entry.get("model") or table.get("default_model") or "") or ("gpt-4o" if prov == "openai" else "default")
            base_url = entry.get("base_url") or table.get("base_url") or None
            effort = entry.get("reasoning_effort")
            is_local = prov.lower() in ("local", "llama", "llama-server", "ollama", "vllm")
            key_count = 1 if is_local else max(1, len(get_api_keys(prov)) or (len(get_api_keys("google")) if prov == "gemini" else 0))
            for index in range(key_count):
                routes.append(
                    RouteConfig(
                        provider=prov,
                        model=model_name,
                        base_url=str(base_url) if base_url else None,  # a role may point at its own server (two local models)
                        params=dict(entry.get("params", table.get("params", {}))),
                        reasoning_effort=str(effort) if effort else None,
                        key_index=index,
                    )
                )
        return routes

    @staticmethod
    def _runnable(chat: Any, output_schema: type[Any] | None, provider: str) -> "Runnable[Any, Any]":
        """One route as a runnable. Only transient failures are retried here: a rate limit (429) or a bad key moves on to the next route at once."""
        try:
            import openai

            transient: tuple[type[BaseException], ...] = (openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError)
            rejected: tuple[type[BaseException], ...] = (openai.BadRequestError,)
        except ImportError:
            transient, rejected = (ConnectionError, TimeoutError), ()
        retry: dict[str, Any] = {"retry_if_exception_type": transient, "stop_after_attempt": 3}
        if output_schema is not None and getattr(chat, "with_structured_output", None) is not None:
            try:
                strict = chat.with_structured_output(output_schema, method="json_schema").with_retry(**retry)
            except Exception:  # noqa: BLE001 - the provider rejects strict json_schema output: use its default mode
                logger.debug("json_schema structured output unsupported by %s; using the default method", provider, exc_info=True)
                return chat.with_structured_output(output_schema).with_retry(**retry)  # type: ignore[no-any-return]
            # strict json_schema is refused at call time for schemas with free-form objects (a dict field): Groq answered 400
            # "additionalProperties:false must be set on every object" and stopped a run. Tool calling accepts those schemas.
            if rejected:
                try:
                    loose = chat.with_structured_output(output_schema, method="function_calling").with_retry(**retry)
                    return strict.with_fallbacks([loose], exceptions_to_handle=rejected)  # type: ignore[no-any-return]
                except Exception:  # noqa: BLE001 - a model without tool calling keeps the strict form only
                    logger.debug("function_calling structured output unsupported by %s", provider, exc_info=True)
            return strict  # type: ignore[no-any-return]
        return chat.with_retry(**retry)  # type: ignore[no-any-return]
