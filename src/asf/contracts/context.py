# FILE: src/asf/contracts/context.py
# ROLE: Defines ContextRequest and ContextPack (IF-11) with the P0-P5 priority tiers.
# ARCH REF: p12 Context & Memory Service; p15 ContextPack; IF-11
# OWNS: Context request/response shapes
# DOES NOT OWN: Assembling packs (src/asf/m5_shared/context/context_service.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/ids.py: TaskId (typed ids)
#   - called by src/asf/m5_shared/context/context_service.py: ContextPack, ContextRequest
#   - called by tests/contracts/test_context.py: ContextTier, ContextRequest, ContextItem, ContextPack
#   - called by src/asf/m4_execution/worker/worker_graph.py: ContextItem, ContextRequest
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
# DONE WHEN: (1) tests/contracts/test_context.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/contracts/context.py` and `uv run mypy src/asf/contracts/context.py` are clean.

from enum import IntEnum

from pydantic import BaseModel, Field

from asf.contracts.ids import TaskId


class ContextTier(IntEnum):
    P0_SPEC = 0
    P1_CAPSULES = 1
    P2_ALLOWED_FILES = 2
    P3_SNIPPETS = 3
    P4_DECISIONS = 4
    P5_FAILURE = 5


class ContextRequest(BaseModel):
    task_id: TaskId
    role: str
    budget_tokens: int
    model_id: str = Field(description="tokenizer is chosen from this model (D-31)")


class ContextItem(BaseModel):
    tier: ContextTier
    source_ref: str
    sha256: str
    tokens: int
    text: str


class ContextPack(BaseModel):
    pack_id: str
    task_id: TaskId
    role: str
    budget_tokens: int
    token_count: int
    items: list[ContextItem]
    dropped: list[str] = Field(default_factory=list)
    token_count_estimated: bool = False
