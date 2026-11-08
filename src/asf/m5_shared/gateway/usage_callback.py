# FILE: src/asf/m5_shared/gateway/usage_callback.py
# ROLE: LangChain callback that records tokens, latency and cost per call into metrics and the attempt ledger.
# ARCH REF: M5; p11; D-06 budgets; D-24
# OWNS: Usage accounting per call
# DOES NOT OWN: Pricing rules (metrics/pricing.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/metrics/collector.py: MetricsCollector (D-24)
#   - imports from src/asf/m5_shared/metrics/pricing.py: price_for (D-27)
#   - called by src/asf/m5_shared/gateway/gateway.py: UsageCallbackHandler
#   - called by tests/m5_shared/gateway/test_usage_callback.py: UsageCallbackHandler
#   - emits/consumes: emits MODEL_CALL and USAGE events via MetricsCollector
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/gateway/test_usage_callback.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/gateway/usage_callback.py` and `uv run mypy src/asf/m5_shared/gateway/usage_callback.py` are clean.

import time
from types import SimpleNamespace
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from asf.m5_shared.metrics.collector import MetricsCollector
from asf.m5_shared.metrics.pricing import price_for


class UsageCallbackHandler(BaseCallbackHandler):
    run_id: str
    task_id: str | None
    role: str
    strategy: str
    collector: MetricsCollector | None
    total_tokens_in: int
    total_tokens_out: int
    total_cost: float
    _start_time: float | None

    def __init__(
        self,
        run_id: str,
        task_id: str | None,
        role: str,
        strategy: str,
        collector: MetricsCollector | None = None,
    ) -> None:
        super().__init__()
        self.run_id = run_id
        self.task_id = task_id
        self.role = role
        self.strategy = strategy
        self.collector = collector
        self.total_tokens_in = 0
        self.total_tokens_out = 0
        self.total_cost = 0.0
        self._start_time = None

    def on_llm_start(
        self,
        serialized: dict[str, Any] | None = None,
        prompts: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self._start_time = time.monotonic()

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        latency_ms = int((time.monotonic() - self._start_time) * 1000) if self._start_time else 0
        self._start_time = None

        tokens_in = 0
        tokens_out = 0
        provider = "unknown"
        model = "unknown"

        llm_output = getattr(response, "llm_output", None) or {}
        if isinstance(llm_output, dict):
            m_val = llm_output.get("model_name", llm_output.get("model"))
            if m_val:
                model = str(m_val)
            usage = llm_output.get("token_usage", llm_output.get("usage"))
            if isinstance(usage, dict):
                tokens_in = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
                tokens_out = int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)

        if not tokens_in and not tokens_out and hasattr(response, "generations"):
            for gen_list in response.generations:
                for gen in gen_list:
                    gen_info = getattr(gen, "generation_info", None) or {}
                    msg = getattr(gen, "message", None)
                    if msg and hasattr(msg, "response_metadata") and isinstance(msg.response_metadata, dict):
                        gen_info = {**gen_info, **msg.response_metadata}
                    usage = gen_info.get("token_usage", gen_info.get("usage"))
                    if isinstance(usage, dict):
                        tokens_in = int(usage.get("prompt_tokens", usage.get("input_tokens", tokens_in)) or 0)
                        tokens_out = int(usage.get("completion_tokens", usage.get("output_tokens", tokens_out)) or 0)
                    if "model_name" in gen_info:
                        model = str(gen_info["model_name"])
                    elif "model" in gen_info:
                        model = str(gen_info["model"])

        cost, is_estimated = price_for(provider, model, tokens_in, tokens_out)
        self.total_tokens_in += tokens_in
        self.total_tokens_out += tokens_out
        self.total_cost += cost

        metric = SimpleNamespace(
            run_id=self.run_id,
            task_id=self.task_id,
            role=self.role,
            provider=provider,
            model=model,
            strategy=self.strategy,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost=cost,
            source="ESTIMATED" if is_estimated else "MEASURED",
            retry_no=0,
        )

        if self.collector is not None:
            self.collector.record_call(metric)  # type: ignore[arg-type]
