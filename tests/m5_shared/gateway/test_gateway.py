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
from typing import Any

import pytest
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel

from asf.m5_shared.gateway.gateway import ModelGateway


class DummySchema(BaseModel):
    summary: str


def _budget() -> Any:
    return SimpleNamespace(
        run_id="run-test", max_remote_tokens=10000, max_local_tokens=10000, max_api_spend=10.0, max_wall_clock_s=3600, max_task_nodes=20,
        used_remote_tokens=0, used_local_tokens=0, used_api_spend=0.0, used_task_nodes=0, alert_fraction=0.8,
    )


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


def test_a_role_can_point_at_its_own_local_server(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Any] = []

    def fake_build(route: Any) -> Any:
        seen.append(route)
        return RunnableLambda(lambda x: x)

    monkeypatch.setattr("asf.m5_shared.gateway.gateway.build_chat_model", fake_build)
    budget = SimpleNamespace(
        run_id="r", max_remote_tokens=10**6, max_local_tokens=10**6, max_api_spend=10.0, max_wall_clock_s=3600, max_task_nodes=20,
        used_remote_tokens=0, used_local_tokens=0, used_api_spend=0.0, used_task_nodes=0, alert_fraction=0.8,
    )
    gw = ModelGateway("local-only", budget)  # type: ignore[arg-type]
    gw.roles["T1"] = {"provider": "local", "model": "tiny", "base_url": "http://127.0.0.1:8081/v1", "params": {"temperature": 0.1}}
    gw.roles["T2"] = {"provider": "local", "model": "coder", "base_url": "http://127.0.0.1:8082/v1"}
    gw.model_for("T1", "rubric")  # type: ignore[arg-type]
    gw.model_for("T2", "code_step")  # type: ignore[arg-type]
    assert [(r.base_url, r.model) for r in seen] == [("http://127.0.0.1:8081/v1", "tiny"), ("http://127.0.0.1:8082/v1", "coder")]
    assert seen[0].params == {"temperature": 0.1}


def test_every_stored_key_and_fallback_becomes_a_route_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """Three Groq keys then a Gemini key give four routes: key 1, 2, 3 of the primary, then the fallback."""
    keys = {"groq": ["g1", "g2", "g3"], "gemini": ["m1"]}
    monkeypatch.setattr("asf.m5_shared.gateway.gateway.get_api_keys", lambda provider: keys.get(provider, []))
    gateway = ModelGateway("free", _budget())
    routes = gateway._routes_for(gateway.roles["reviewer"])
    assert [(r.provider, r.model.split("/")[-1], r.key_index) for r in routes] == [
        ("groq", "gpt-oss-20b", 0), ("groq", "gpt-oss-20b", 1), ("groq", "gpt-oss-20b", 2),
        ("groq", "gpt-oss-120b", 0), ("groq", "gpt-oss-120b", 1), ("groq", "gpt-oss-120b", 2), ("gemini", "gemini-3.5-flash", 0),
    ]
    assert routes[0].reasoning_effort == "low"
    assert routes[0].base_url == "https://api.groq.com/openai/v1"


def test_a_missing_primary_key_falls_through_to_the_next_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no Groq key but a Gemini key the reviewer still gets a model instead of an error."""
    keys = {"gemini": ["m1"]}
    monkeypatch.setattr("asf.m5_shared.gateway.gateway.get_api_keys", lambda provider: keys.get(provider, []))
    monkeypatch.setattr("asf.m5_shared.gateway.providers.get_api_keys", lambda provider: keys.get(provider, []))
    monkeypatch.setattr("asf.m5_shared.gateway.providers.get_api_key", lambda provider: (keys.get(provider) or [""])[0] or None)
    assert ModelGateway("free", _budget()).model_for("reviewer", "review") is not None  # type: ignore[arg-type]


def test_a_schema_the_provider_rejects_at_call_time_is_retried_with_tool_calling() -> None:
    """Groq answers 400 to strict json_schema for a schema with a dict field; the same route then works through tool calling."""
    import httpx
    import openai

    rejected = openai.BadRequestError("additionalProperties:false must be set", response=httpx.Response(400, request=httpx.Request("POST", "http://x")), body=None)  # type: ignore[arg-type]

    def refuse(_: Any) -> Any:
        raise rejected

    class FakeChat:
        methods: list[str] = []

        def with_structured_output(self, schema: Any, method: str = "default") -> Any:
            self.methods.append(method)
            return RunnableLambda(refuse) if method == "json_schema" else RunnableLambda(lambda _: DummySchema(summary="via tools"))

    chat = FakeChat()
    runnable = ModelGateway._runnable(chat, DummySchema, "groq")
    assert runnable.invoke("go") == DummySchema(summary="via tools")
    assert chat.methods == ["json_schema", "function_calling"]


def test_a_run_without_a_profile_uses_the_active_profile_of_models_toml() -> None:
    """`factory run resume` carries no --profile; it fell back to "hybrid" and asked for an OpenAI key the user never configured."""
    assert ModelGateway.default_profile_name() == "free"
