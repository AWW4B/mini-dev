# FILE: src/asf/contracts/models.py
# ROLE: Defines model roles, InferenceRequest/Result (IF-12), SlotLease (IF-13) and ModelProfile.
# ARCH REF: p11; IF-12; IF-13; IF-20 ModelProfile; D-07; D-08; D-09
# OWNS: Model-call and lease shapes
# DOES NOT OWN: Routing (gateway) and slot management (runtime)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/ids.py: LeaseId (typed ids)
#   - called by src/asf/m5_shared/gateway/gateway.py: ModelRole
#   - called by src/asf/m5_shared/runtime/local_runtime.py: SlotLease, SlotLeaseRequest
#   - called by src/asf/m5_shared/runtime/calibration.py: ModelProfile
#   - called by src/asf/m3_orchestration/decomposition/sizer.py: ModelProfile
#   - called by src/asf/m4_execution/worker/worker_graph.py: SlotLease
#   - called by tests/contracts/test_models.py: ModelRole, InferenceRequest, InferenceResult, SlotLeaseRequest, SlotLease, ModelProfile
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
# DONE WHEN: (1) tests/contracts/test_models.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/contracts/models.py` and `uv run mypy src/asf/contracts/models.py` are clean.

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from asf.contracts.ids import LeaseId


class ModelRole(StrEnum):
    T1 = "T1"          # tiny local: log summaries, error classification, rubric (never tests, A-4)
    T2 = "T2"          # local coder
    T3 = "T3"          # planning tier (remote by default)
    REVIEWER = "reviewer"


class InferenceRequest(BaseModel):
    """IF-12."""
    role: ModelRole
    purpose: str = Field(description="e.g. split_proposal, structure_brief, code_step")
    output_schema: dict[str, Any] | None = None
    max_output_tokens: int = 2048
    budget_key: str
    lease_id: LeaseId | None = None


class InferenceResult(BaseModel):
    provider: str
    model: str
    content: Any
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost: float | None
    cost_estimated: bool


class SlotLeaseRequest(BaseModel):
    """IF-13 request."""
    model_id: str
    ctx_tokens: int
    ttl_s: int = 600
    priority: int = 0


class SlotLease(BaseModel):
    """IF-13 grant."""
    lease_id: LeaseId
    model_id: str
    ctx_tokens: int
    expires_at_monotonic: float
    base_url: str = Field(description="OpenAI-compatible base URL of the backend serving this slot")


class ModelProfile(BaseModel):
    """IF-20 ModelProfile, produced by calibration (p11)."""
    model_id: str
    backend: str
    c_eff_tokens: int
    max_slots: int = Field(ge=1, le=2)
    tokens_per_s: float
    vram_mb_by_ctx: dict[int, int] = Field(default_factory=dict)
    success_by_size_bucket: dict[str, float] = Field(default_factory=dict)
