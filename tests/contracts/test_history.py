# FILE: tests/contracts/test_history.py
# ROLE: Tests that prove src/asf/contracts/history.py meets its DONE WHEN conditions.
# ARCH REF: p02 Project History; p09; IF-24; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/history.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/history.py: HistoryQuery, RunSummary, HistoryResult (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_history.py` on Windows and Linux once src/asf/contracts/history.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_history.py` and `uv run mypy tests/contracts/test_history.py` are clean.



import pytest
from pydantic import ValidationError

from asf.contracts.history import HistoryQuery, HistoryResult, RunSummary


def test_query_defaults_to_the_fifty_most_recent_without_filters() -> None:
    q = HistoryQuery()
    assert q.project_id is None and q.run_id is None
    assert q.limit == 50


def test_query_accepts_filters() -> None:
    q = HistoryQuery.model_validate({"project_id": "p1", "run_id": "r1", "limit": 5})
    assert (q.project_id, q.run_id, q.limit) == ("p1", "r1", 5)


def test_summary_requires_all_fields_and_flags_estimated_cost() -> None:
    data = {"run_id": "r1", "project_id": "p1", "status": "done", "last_activity": "2026-11-12", "cost": 1.5, "cost_estimated": True}
    assert RunSummary.model_validate(data).cost_estimated is True
    for missing in data:
        partial = dict(data)
        del partial[missing]
        with pytest.raises(ValidationError):
            RunSummary.model_validate(partial)


def test_result_round_trip_and_empty_result() -> None:
    assert HistoryResult.model_validate({"runs": []}).runs == []
    row = {"run_id": "r1", "project_id": "p1", "status": "done", "last_activity": "t", "cost": 0.0, "cost_estimated": False}
    res = HistoryResult.model_validate({"runs": [row]})
    assert HistoryResult.model_validate_json(res.model_dump_json()) == res
