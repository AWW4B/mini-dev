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

from typing import Any

from langchain_core.callbacks import BaseCallbackHandler


class UsageCallbackHandler(BaseCallbackHandler):
    def __init__(self, run_id: str, task_id: str | None, role: str, strategy: str) -> None:
        raise NotImplementedError

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        raise NotImplementedError
