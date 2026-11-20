# FILE: src/asf/m5_shared/gateway/usage_callback.py
# ROLE: LangChain callback that records tokens, latency and cost per call into metrics and the attempt ledger.
# ARCH REF: M5; p11; D-06 budgets; D-24
# OWNS: Usage accounting per call
# DOES NOT OWN: Pricing rules (metrics/pricing.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/metrics/collector.py: MetricsCollector (D-24)
#   - imports from src/asf/m5_shared/metrics/pricing.py: price_for (D-27)
#   - imports from src/asf/m5_shared/trace.py: trace_event, clip, current_task (every model call with tokens, latency and the limits used so far)
#   - called by src/asf/m5_shared/gateway/gateway.py: UsageCallbackHandler
#   - called by src/asf/m3_orchestration/run_graph.py: drain_call_metrics
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

import logging
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from asf.m5_shared.metrics.collector import MetricsCollector
from asf.m5_shared.metrics.pricing import price_for
from asf.m5_shared.trace import clip, current_task, trace_event

logger = logging.getLogger(__name__)

_pending: list[tuple[Any, ...]] = []
_pending_lock = threading.Lock()


def drain_call_metrics() -> list[tuple[Any, ...]]:
    """The call_metrics rows queued by model calls since the last drain (any thread queues; the run's main thread writes them)."""
    with _pending_lock:
        rows = list(_pending)
        _pending.clear()
    return rows


def _provider_of(serialized: dict[str, Any] | None) -> str:
    """Which service a chat model talks to, from its client settings (the callback is not told the route)."""
    info = serialized or {}
    kwargs = info.get("kwargs", {}) if isinstance(info.get("kwargs"), dict) else {}
    base = str(kwargs.get("openai_api_base") or kwargs.get("base_url") or "")
    ident = info.get("id") or []
    if "Anthropic" in str(ident):
        return "anthropic"
    for needle, name in (("127.0.0.1", "local"), ("localhost", "local"), ("groq", "groq"), ("generativelanguage", "gemini"), ("x.ai", "xai"), ("openrouter", "openrouter"), ("mistral", "mistral"), ("openai.com", "openai")):
        if needle in base:
            return name
    return "dummy" if "Dummy" in str(ident) else ("openai" if not base else base.split("//")[-1].split("/")[0])


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
        budget: Any = None,
        metrics_db: Path | None = None,
    ) -> None:
        super().__init__()
        self.budget = budget
        self.metrics_db = metrics_db
        self._provider = "unknown"
        self._prompt_chars = 0
        self._prompt_preview = ""
        self.run_id = run_id
        self.task_id = task_id
        self.role = role
        self.strategy = strategy
        self.collector = collector
        self.total_tokens_in = 0
        self.total_tokens_out = 0
        self.total_cost = 0.0
        self._start_time = None

    def on_chat_model_start(self, serialized: dict[str, Any] | None = None, messages: Any = None, **kwargs: Any) -> None:
        """Chat models report here, not through on_llm_start: without this the latency was always 0 and the provider unknown."""
        self._start_time = time.monotonic()
        self._provider = _provider_of(serialized)
        flat = [m for batch in (messages or []) for m in batch]
        self._prompt_chars = sum(len(str(getattr(m, "content", ""))) for m in flat)
        self._prompt_preview = str(getattr(flat[-1], "content", ""))[:400] if flat else ""

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
        provider = self._provider
        model = "unknown"
        reply = ""

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

        for gen_list in getattr(response, "generations", None) or []:
            for gen in gen_list:
                reply = reply or str(getattr(gen, "text", "") or "")
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

        self._account(metric, provider, model, tokens_in, tokens_out, cost, latency_ms, reply)
        if self.collector is not None:
            self.collector.record_call(metric)  # type: ignore[arg-type]

    def _account(self, metric: Any, provider: str, model: str, tokens_in: int, tokens_out: int, cost: float, latency_ms: int, reply: str) -> None:
        """Count the call against the run's limits, store it in call_metrics and write it to the trace with the limits used so far."""
        budget = self.budget
        limits: dict[str, Any] = {}
        if budget is not None:
            try:
                total = tokens_in + tokens_out
                if provider == "local":
                    budget.used_local_tokens += total
                else:
                    budget.used_remote_tokens += total
                budget.used_api_spend += cost
                limits = {
                    "remote_tokens": f"{budget.used_remote_tokens}/{budget.max_remote_tokens}",
                    "local_tokens": f"{budget.used_local_tokens}/{budget.max_local_tokens}",
                    "api_spend": f"{budget.used_api_spend:.4f}/{budget.max_api_spend}",
                }
            except (AttributeError, TypeError):
                limits = {}
        if self.metrics_db is not None:
            # queued, not written here: a second connection committing to state.db made the main connection's next write fail with
            # "database is locked" (WAL: its read snapshot was stale). The run's main thread drains the queue with its own connection.
            with _pending_lock:
                _pending.append(
                    (self.run_id, self.task_id or current_task(), provider, model, tokens_in, tokens_out, cost, latency_ms, datetime.now(UTC).isoformat(), self.role, self.strategy,
                     1 if metric.source == "ESTIMATED" else 0, 0)
                )
        trace_event(
            "gateway", "model_call", role=self.role, provider=provider, model=model, task=self.task_id or current_task(), purpose=self.strategy,
            tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=latency_ms, cost=cost, prompt_chars=self._prompt_chars, prompt_tail=clip(self._prompt_preview, 300),
            reply=clip(reply, 4000), reply_chars=len(reply), limits_used=limits,
        )
