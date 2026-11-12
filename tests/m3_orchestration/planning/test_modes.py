# FILE: tests/m3_orchestration/planning/test_modes.py
# ROLE: Tests that prove src/asf/m3_orchestration/planning/modes.py meets its DONE WHEN conditions.
# ARCH REF: M3; p04 modes; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/planning/modes.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/planning/modes.py: PlanMode, select_mode (unit under test)
#   - imports from src/asf/contracts/requests.py: StructuredRequest (request fixtures)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/planning/test_modes.py` on Windows and Linux once src/asf/m3_orchestration/planning/modes.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/planning/test_modes.py` and `uv run mypy tests/m3_orchestration/planning/test_modes.py` are clean.

import pytest

from asf.contracts.requests import StructuredRequest
from asf.m3_orchestration.planning.modes import PlanMode, select_mode


def _request(task_type: str) -> StructuredRequest:
    return StructuredRequest.model_validate({"request_id": "q", "project_id": "p", "task_type": task_type, "requirements": []})


def test_plan_modes() -> None:
    assert {m.value for m in PlanMode} == {"design", "diagnosis", "impact"}


@pytest.mark.parametrize(
    ("task_type", "mode"),
    [
        ("new_build", PlanMode.DESIGN),
        ("debug", PlanMode.DIAGNOSIS),
        ("feature", PlanMode.IMPACT),
        ("refactor", PlanMode.IMPACT),
        ("test_generation", PlanMode.IMPACT),
        ("code_docs", PlanMode.IMPACT),
    ],
)
def test_the_task_type_selects_the_mode(task_type: str, mode: PlanMode) -> None:
    assert select_mode(_request(task_type)) is mode


def test_an_unsupported_request_has_no_mode() -> None:
    with pytest.raises(ValueError, match="not supported"):
        select_mode(_request("unsupported"))
