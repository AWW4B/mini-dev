# FILE: src/asf/contracts/history.py
# ROLE: Defines HistoryQuery and HistoryResult (IF-24).
# ARCH REF: p02 Project History; p09; IF-24
# OWNS: History shapes
# DOES NOT OWN: Queries (state_store)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/ids.py: ProjectId, RunId (typed ids)
#   - called by src/asf/m5_shared/state_store/store.py: HistoryQuery, HistoryResult
#   - called by src/asf/cli/commands/history.py: HistoryQuery
#   - called by tests/contracts/test_history.py: HistoryQuery, RunSummary, HistoryResult
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. This file is declarations only: Pydantic models, enums and type aliases. Add field validators only where the docstring of a field states a constraint.
#   6. Every model must round-trip through model_dump_json() / model_validate_json() unchanged; the JSON Schema exported from these models is the published contract (D-39: no hand-written JSON).
#   7. Changing a field name or type is a contract change: stop and report instead.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; business logic; I/O; imports from asf.m1-m5 packages, asf.cli, asf.web or asf.platform
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/contracts/test_history.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/contracts/history.py` and `uv run mypy src/asf/contracts/history.py` are clean.

from pydantic import BaseModel

from asf.contracts.ids import ProjectId, RunId


class HistoryQuery(BaseModel):
    """IF-24 request."""
    project_id: ProjectId | None = None
    run_id: RunId | None = None
    limit: int = 50


class RunSummary(BaseModel):
    run_id: RunId
    project_id: ProjectId
    status: str
    last_activity: str
    cost: float
    cost_estimated: bool


class HistoryResult(BaseModel):
    """IF-24 response."""
    runs: list[RunSummary]
