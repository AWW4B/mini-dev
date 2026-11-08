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

from typing import Any

from langchain_core.runnables import Runnable

from asf.contracts.budget import RunBudget
from asf.contracts.models import ModelRole


class ModelGateway:
    def __init__(self, profile_name: str, budget: RunBudget) -> None:
        raise NotImplementedError

    def model_for(self, role: ModelRole, purpose: str, output_schema: type[Any] | None = None, task_id: str | None = None) -> Runnable[Any, Any]:
        raise NotImplementedError

    def baseline_warnings(self) -> list[str]:
        """D-09: warn (never block) when the profile lacks 2 API providers, a local coder or the tiny model."""
        raise NotImplementedError
