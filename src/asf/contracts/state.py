# FILE: src/asf/contracts/state.py
# ROLE: Defines StateCommit (IF-16), the single write request accepted by the State Store.
# ARCH REF: p09 Project State Store; IF-16
# OWNS: State commit shape
# DOES NOT OWN: Transactions (state_store/store.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/events.py: EventEnvelope (outbox events committed in the same transaction)
#   - called by src/asf/m5_shared/state_store/store.py: StateCommit
#   - called by tests/contracts/test_state.py: StateCommit
#   - called by src/asf/m5_shared/state_store/recovery.py: StateCommit
#   - called by src/asf/m4_execution/integration/integrator.py: StateCommit
#   - called by src/asf/m3_orchestration/decomposition/frontier.py: StateCommit
#   - called by src/asf/m3_orchestration/run_control.py: StateCommit
#   - called by src/asf/m3_orchestration/run_graph.py: StateCommit
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
# DONE WHEN: (1) tests/contracts/test_state.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/contracts/state.py` and `uv run mypy src/asf/contracts/state.py` are clean.

from typing import Any

from pydantic import BaseModel, Field

from asf.contracts.events import EventEnvelope


class StateCommit(BaseModel):
    """IF-16: one entity mutation plus the events it causes, applied atomically."""
    entity: str
    entity_id: str
    expected_version: int | None = Field(description="None = create")
    mutation: dict[str, Any]
    events: list[EventEnvelope] = Field(default_factory=list)
