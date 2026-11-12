# FILE: src/asf/m3_orchestration/planning/modes.py
# ROLE: Selects the planning mode from the StructuredRequest: DESIGN, DIAGNOSIS or IMPACT/REFACTOR.
# ARCH REF: M3; p04 modes
# OWNS: Mode selection
# DOES NOT OWN: Planning itself
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/requests.py: StructuredRequest, TaskType (input)
#   - called by src/asf/m3_orchestration/planning/planner_graph.py: select_mode
#   - called by tests/m3_orchestration/planning/test_modes.py: PlanMode, select_mode
#   - called by src/asf/m3_orchestration/run_graph.py: select_mode
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use these Agent Skills (load via SkillsRegistry): skills/reproduce-bug-as-failing-test/SKILL.md, skills/characterisation-tests/SKILL.md.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/planning/test_modes.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/planning/modes.py` and `uv run mypy src/asf/m3_orchestration/planning/modes.py` are clean.

from enum import StrEnum

from asf.contracts.requests import StructuredRequest, TaskType


class PlanMode(StrEnum):
    DESIGN = "design"
    DIAGNOSIS = "diagnosis"
    IMPACT = "impact"


# new build -> DESIGN; debug -> DIAGNOSIS (reproduce as a failing test, then localise);
# feature, refactor, test generation and docs -> IMPACT (contract delta, characterisation tests first).
_MODES: dict[TaskType, PlanMode] = {
    TaskType.NEW_BUILD: PlanMode.DESIGN,
    TaskType.DEBUG: PlanMode.DIAGNOSIS,
    TaskType.FEATURE: PlanMode.IMPACT,
    TaskType.REFACTOR: PlanMode.IMPACT,
    TaskType.TEST_GENERATION: PlanMode.IMPACT,
    TaskType.CODE_DOCS: PlanMode.IMPACT,
}


def select_mode(request: StructuredRequest) -> PlanMode:
    mode = _MODES.get(request.task_type)
    if mode is None:
        raise ValueError(f"No planning mode for task type '{request.task_type}'; the request is not supported")
    return mode
