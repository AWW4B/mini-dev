# FILE: src/asf/m3_orchestration/planning/strategies.py
# ROLE: Planner strategies: single_pass, self_critique(n), plan_then_verify.
# ARCH REF: M3; p04; D-09 strategies
# OWNS: Strategy implementations
# DOES NOT OWN: Prompt content of skills
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (IF-12 model calls)
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

from typing import Any, Literal

from asf.m5_shared.gateway.gateway import ModelGateway

PlannerStrategyName = Literal["single_pass", "self_critique", "plan_then_verify"]


def run_planner_strategy(name: PlannerStrategyName, gateway: ModelGateway, prompt: str, output_schema: type[Any], rounds: int = 2) -> Any:
    raise NotImplementedError
