# FILE: tests/m5_shared/gateway/test_gateway.py
# ROLE: Tests that prove src/asf/m5_shared/gateway/gateway.py meets its DONE WHEN conditions.
# ARCH REF: M5; p11 Model Gateway; IF-12 InferenceRequest; D-07; D-09; D-10; A-4; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/gateway/gateway.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/gateway/test_gateway.py` on Windows and Linux once src/asf/m5_shared/gateway/gateway.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/gateway/test_gateway.py` and `uv run mypy tests/m5_shared/gateway/test_gateway.py` are clean.


from types import SimpleNamespace

import pytest
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from asf.m5_shared.gateway.gateway import ModelGateway


class DummySchema(BaseModel):
    summary: str


def test_model_gateway_meets_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prove ModelGateway behaves as declared in src/asf/m5_shared/gateway/gateway.py."""
    monkeypatch.setenv("FACTORY_OPENAI_API_KEY", "mock-openai-key")  # noqa: S106

    budget = SimpleNamespace(
        run_id="run-test",
        max_remote_tokens=10000,
        max_local_tokens=10000,
        max_api_spend=10.0,
        max_wall_clock_s=3600,
        max_task_nodes=20,
        used_remote_tokens=100,
        used_local_tokens=100,
        used_api_spend=0.5,
        used_task_nodes=1,
        alert_fraction=0.8,
    )

    # 1. Baseline warnings
    hybrid_gw = ModelGateway("hybrid", budget)  # type: ignore[arg-type]
    assert isinstance(hybrid_gw.baseline_warnings(), list)

    local_gw = ModelGateway("local-only", budget)  # type: ignore[arg-type]
    local_warns = local_gw.baseline_warnings()
    assert any("2 API providers" in w for w in local_warns)

    # 2. Refuse role T1 for purpose "acceptance_tests" (A-4)
    with pytest.raises(ValueError, match="acceptance_tests"):
        hybrid_gw.model_for("T1", "acceptance_tests")  # type: ignore[arg-type]

    # 3. Model for valid role returns Runnable
    runnable = hybrid_gw.model_for("T2", "code_step")  # type: ignore[arg-type]
    assert isinstance(runnable, Runnable)

    # 4. Structured output runnable
    structured_runnable = hybrid_gw.model_for("T2", "code_step", output_schema=DummySchema)  # type: ignore[arg-type]
    assert isinstance(structured_runnable, Runnable)

    # 5. Budget exceeded raises error
    exhausted_budget = SimpleNamespace(
        run_id="run-exhausted",
        max_remote_tokens=1000,
        max_local_tokens=1000,
        max_api_spend=5.0,
        max_wall_clock_s=3600,
        max_task_nodes=20,
        used_remote_tokens=2000,
        used_local_tokens=500,
        used_api_spend=10.0,
        used_task_nodes=1,
        alert_fraction=0.8,
    )
    exhausted_gw = ModelGateway("hybrid", exhausted_budget)  # type: ignore[arg-type]
    with pytest.raises(Exception, match="[Bb]udget"):
        exhausted_gw.model_for("T3", "planning")  # type: ignore[arg-type]
