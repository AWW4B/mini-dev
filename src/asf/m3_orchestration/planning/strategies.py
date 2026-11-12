# FILE: src/asf/m3_orchestration/planning/strategies.py
# ROLE: Planner strategies: single_pass, self_critique(n), plan_then_verify.
# ARCH REF: M3; p04; D-09 strategies
# OWNS: Strategy implementations
# DOES NOT OWN: Prompt content of skills
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (IF-12 model calls)
#   - imports from src/asf/contracts/errors.py: InvalidModelOutput (validation re-asks exhausted)
#   - called by src/asf/m3_orchestration/planning/planner_graph.py: run_planner_strategy
#   - called by tests/m3_orchestration/planning/test_strategies.py: run_planner_strategy, PlannerStrategyName
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/planning/test_strategies.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/planning/strategies.py` and `uv run mypy src/asf/m3_orchestration/planning/strategies.py` are clean.

import json
import logging
from typing import Any, Literal, cast

from pydantic import ValidationError

from asf.contracts.errors import InvalidModelOutput
from asf.m5_shared.gateway.gateway import ModelGateway

logger = logging.getLogger(__name__)

PlannerStrategyName = Literal["single_pass", "self_critique", "plan_then_verify"]

FORMAT_REPAIRS = 2
_NO_ISSUES = "NO_ISSUES"


def _dump(plan: Any) -> str:
    return str(plan.model_dump_json()) if hasattr(plan, "model_dump_json") else json.dumps(plan, default=str)


def _coerce(raw: Any, schema: type[Any]) -> Any:
    """Turn a model reply (schema instance, dict, message or text containing JSON) into a validated schema instance."""
    if isinstance(raw, schema):
        return raw
    if isinstance(raw, dict):
        return schema.model_validate(raw)
    text = str(getattr(raw, "content", raw))
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("the reply contains no JSON object")
    return schema.model_validate(json.loads(text[start : end + 1]))


def _ask(gateway: ModelGateway, role: str, prompt: str, schema: type[Any]) -> Any:
    """One structured planner call, re-asking with the validator's complaint up to FORMAT_REPAIRS times."""
    model = gateway.model_for(cast(Any, role), purpose="plan", output_schema=schema)
    current = prompt
    problem = ""
    for _ in range(FORMAT_REPAIRS + 1):
        try:
            return _coerce(model.invoke(current), schema)
        except (ValidationError, ValueError) as err:
            problem = str(err)[:1500]
            current = f"{prompt}\n\nYour previous answer was rejected by the validator:\n{problem}\nAnswer again with valid output."
    raise InvalidModelOutput(f"The planner did not produce valid output after {FORMAT_REPAIRS + 1} tries: {problem}")


def _critique(gateway: ModelGateway, role: str, prompt: str, plan: Any) -> str:
    """Concrete defects found by a second look at the plan, or '' when there are none."""
    reply = gateway.model_for(cast(Any, role), purpose="plan_critique").invoke(
        "Review this plan against the task. List only concrete defects (missing requirement coverage, an interface nobody "
        f"produces, a dependency cycle, an unclear module). Answer {_NO_ISSUES} if there are none.\n\n"
        f"TASK:\n{prompt}\n\nPLAN:\n{_dump(plan)}"
    )
    text = str(getattr(reply, "content", reply)).strip()
    return "" if not text or _NO_ISSUES in text.upper() else text


def _revise(gateway: ModelGateway, role: str, prompt: str, plan: Any, issues: str, schema: type[Any]) -> Any:
    return _ask(gateway, role, f"{prompt}\n\nPREVIOUS PLAN:\n{_dump(plan)}\n\nISSUES TO FIX (change only what these require):\n{issues}", schema)


def run_planner_strategy(
    name: PlannerStrategyName,
    gateway: ModelGateway,
    prompt: str,
    output_schema: type[Any],
    rounds: int = 2,
    *,
    role: str = "T3",
) -> Any:
    """single_pass: one call. self_critique: up to ``rounds`` critique-and-revise passes. plan_then_verify: one verify pass."""
    if name not in ("single_pass", "self_critique", "plan_then_verify"):
        raise ValueError(f"unknown planner strategy '{name}'")
    plan = _ask(gateway, role, prompt, output_schema)
    if name == "single_pass":
        return plan
    if name == "self_critique":
        for round_no in range(max(0, rounds)):
            issues = _critique(gateway, role, prompt, plan)
            if not issues:
                break
            logger.info("planner self-critique round %d found issues", round_no + 1)
            plan = _revise(gateway, role, prompt, plan, issues, output_schema)
        return plan
    if name == "plan_then_verify":
        issues = _critique(gateway, role, prompt, plan)
        return _revise(gateway, role, prompt, plan, issues, output_schema) if issues else plan
    raise AssertionError(name)  # unreachable: the name was validated above
