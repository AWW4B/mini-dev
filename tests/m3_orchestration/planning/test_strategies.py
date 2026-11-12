# FILE: tests/m3_orchestration/planning/test_strategies.py
# ROLE: Tests that prove src/asf/m3_orchestration/planning/strategies.py meets its DONE WHEN conditions.
# ARCH REF: M3; p04; D-09 strategies; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/planning/strategies.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/planning/strategies.py: run_planner_strategy, PlannerStrategyName (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/planning/test_strategies.py` on Windows and Linux once src/asf/m3_orchestration/planning/strategies.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/planning/test_strategies.py` and `uv run mypy tests/m3_orchestration/planning/test_strategies.py` are clean.

import json
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from asf.m3_orchestration.planning.strategies import PlannerStrategyName, run_planner_strategy


class Plan(BaseModel):
    steps: list[str]


class _Gateway:
    """Scripted planner: `plans` are the structured replies in order, `critiques` the critique answers in order."""

    def __init__(self, plans: list[Any], critiques: list[str] | None = None) -> None:
        self.plans = list(plans)
        self.critiques = list(critiques or [])
        self.calls: list[tuple[str, str]] = []
        self.prompts: list[str] = []

    def model_for(self, role: Any, purpose: str, output_schema: Any = None, task_id: Any = None) -> Any:
        self.calls.append((role, purpose))
        outer = self

        class _Model:
            def invoke(self, prompt: str) -> Any:
                outer.prompts.append(prompt)
                if purpose == "plan_critique":
                    return SimpleNamespace(content=outer.critiques.pop(0) if outer.critiques else "NO_ISSUES")
                return outer.plans.pop(0)

        return _Model()


def _run(name: PlannerStrategyName, gateway: _Gateway, **kwargs: Any) -> Any:
    return run_planner_strategy(name, gateway, "plan the thing", Plan, **kwargs)  # type: ignore[arg-type]


def test_single_pass_is_one_planner_call() -> None:
    gateway = _Gateway([Plan(steps=["a"])])
    assert _run("single_pass", gateway).steps == ["a"]
    assert gateway.calls == [("T3", "plan")]


def test_self_critique_revises_until_the_critique_finds_nothing() -> None:
    gateway = _Gateway([Plan(steps=["a"]), Plan(steps=["a", "b"])], ["step b is missing"])
    assert _run("self_critique", gateway).steps == ["a", "b"]
    assert [c[1] for c in gateway.calls] == ["plan", "plan_critique", "plan", "plan_critique"]
    assert "step b is missing" in gateway.prompts[2] and "PREVIOUS PLAN" in gateway.prompts[2]


def test_self_critique_is_bounded_by_rounds() -> None:
    gateway = _Gateway([Plan(steps=[str(i)]) for i in range(5)], ["still wrong"] * 5)
    assert _run("self_critique", gateway, rounds=2).steps == ["2"]
    assert sum(1 for c in gateway.calls if c[1] == "plan_critique") == 2


def test_plan_then_verify_revises_at_most_once() -> None:
    gateway = _Gateway([Plan(steps=["a"]), Plan(steps=["fixed"])], ["defect"])
    assert _run("plan_then_verify", gateway).steps == ["fixed"]
    clean = _Gateway([Plan(steps=["a"])], ["NO_ISSUES"])
    assert _run("plan_then_verify", clean).steps == ["a"]


def test_replies_may_be_dicts_or_text_with_json() -> None:
    assert _run("single_pass", _Gateway([{"steps": ["x"]}])).steps == ["x"]
    text = SimpleNamespace(content="Here is the plan: " + json.dumps({"steps": ["y"]}) + " done")
    assert _run("single_pass", _Gateway([text])).steps == ["y"]


def test_an_invalid_reply_is_re_asked_with_the_validator_message() -> None:
    gateway = _Gateway([{"steps": "not a list"}, Plan(steps=["ok"])])
    assert _run("single_pass", gateway).steps == ["ok"]
    assert "rejected by the validator" in gateway.prompts[1]


def test_three_invalid_replies_raise_invalid_model_output() -> None:
    gateway = _Gateway([{"nope": 1}, "no json", {"steps": 3}])
    with pytest.raises(Exception) as info:  # noqa: PT011 - InvalidModelOutput lives in contracts, which this test does not import
        _run("single_pass", gateway)
    assert type(info.value).__name__ == "InvalidModelOutput"


def test_the_degraded_role_is_passed_through() -> None:
    gateway = _Gateway([Plan(steps=["a"])])
    _run("single_pass", gateway, role="T2")
    assert gateway.calls == [("T2", "plan")]


def test_an_unknown_strategy_is_rejected_before_any_model_call() -> None:
    gateway = _Gateway([])
    with pytest.raises(ValueError):
        _run("magic", gateway)  # type: ignore[arg-type]
    assert gateway.calls == []
