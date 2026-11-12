# FILE: tests/contracts/test_budget.py
# ROLE: Tests that prove src/asf/contracts/budget.py meets its DONE WHEN conditions.
# ARCH REF: p06 budgets; p15 RunBudget; D-27; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/budget.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/budget.py: RunBudget (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_budget.py` on Windows and Linux once src/asf/contracts/budget.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_budget.py` and `uv run mypy tests/contracts/test_budget.py` are clean.


from typing import Any

import pytest
from pydantic import ValidationError

from asf.contracts.budget import RunBudget


def _valid() -> dict[str, Any]:
    return {
        "run_id": "run_1",
        "max_remote_tokens": 1000,
        "max_local_tokens": 5000,
        "max_api_spend": 2.5,
        "max_wall_clock_s": 3600,
        "max_task_nodes": 50,
    }


def test_usage_counters_and_alert_fraction_have_defaults() -> None:
    budget = RunBudget.model_validate(_valid())
    assert budget.used_remote_tokens == 0
    assert budget.used_local_tokens == 0
    assert budget.used_api_spend == 0.0
    assert budget.used_task_nodes == 0
    assert budget.alert_fraction == 0.8


@pytest.mark.parametrize("missing", sorted(_valid()))
def test_every_limit_and_the_run_id_are_required(missing: str) -> None:
    data = _valid()
    del data[missing]
    with pytest.raises(ValidationError):
        RunBudget.model_validate(data)


def test_non_numeric_limit_is_rejected() -> None:
    data = _valid()
    data["max_remote_tokens"] = "lots"
    with pytest.raises(ValidationError):
        RunBudget.model_validate(data)


def test_usage_counts_independently_per_instance() -> None:
    a = RunBudget.model_validate(_valid())
    b = RunBudget.model_validate(_valid())
    a.used_remote_tokens += 10
    assert b.used_remote_tokens == 0


def test_json_round_trip_is_lossless() -> None:
    budget = RunBudget.model_validate({**_valid(), "used_api_spend": 0.25, "alert_fraction": 0.5})
    assert RunBudget.model_validate_json(budget.model_dump_json()) == budget
