# FILE: tests/m5_shared/gateway/test_usage_callback.py
# ROLE: Tests that prove src/asf/m5_shared/gateway/usage_callback.py meets its DONE WHEN conditions.
# ARCH REF: M5; p11; D-06 budgets; D-24; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/gateway/usage_callback.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/gateway/usage_callback.py: UsageCallbackHandler (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/gateway/test_usage_callback.py` on Windows and Linux once src/asf/m5_shared/gateway/usage_callback.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/gateway/test_usage_callback.py` and `uv run mypy tests/m5_shared/gateway/test_usage_callback.py` are clean.


from types import SimpleNamespace
from typing import Any

from asf.m5_shared.gateway.usage_callback import UsageCallbackHandler


class FakeCollector:
    def __init__(self) -> None:
        self.recorded_calls: list[Any] = []

    def record_call(self, metric: Any) -> None:
        self.recorded_calls.append(metric)


def test_usage_callback_handler_meets_contract() -> None:
    """Prove UsageCallbackHandler behaves as declared in src/asf/m5_shared/gateway/usage_callback.py."""
    collector = FakeCollector()
    handler = UsageCallbackHandler(
        run_id="run-1",
        task_id="task-1",
        role="developer",
        strategy="tool_loop",
        collector=collector,  # type: ignore[arg-type]
    )

    assert handler.run_id == "run-1"
    assert handler.task_id == "task-1"
    assert handler.role == "developer"
    assert handler.strategy == "tool_loop"
    assert handler.total_tokens_in == 0
    assert handler.total_tokens_out == 0

    # Simulate LLM start and end
    handler.on_llm_start({})

    fake_response = SimpleNamespace(
        llm_output={
            "model_name": "gpt-4o",
            "token_usage": {
                "prompt_tokens": 120,
                "completion_tokens": 40,
            },
        }
    )
    handler.on_llm_end(fake_response)

    assert handler.total_tokens_in == 120
    assert handler.total_tokens_out == 40
    assert len(collector.recorded_calls) == 1

    metric = collector.recorded_calls[0]
    assert metric.run_id == "run-1"
    assert metric.task_id == "task-1"
    assert metric.role == "developer"
    assert metric.strategy == "tool_loop"
    assert metric.tokens_in == 120
    assert metric.tokens_out == 40
    assert metric.latency_ms >= 0
