# FILE: src/asf/contracts/metrics.py
# ROLE: Defines call/tool metric rows, limit events, MetricsSnapshot (IF-19) and ResourceAdvisory (IF-20).
# ARCH REF: p10 Metrics; IF-19; IF-20; D-24; D-27
# OWNS: Metric shapes
# DOES NOT OWN: Aggregation (m5_shared/metrics)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/ids.py: RunId, TaskId (typed ids)
#   - called by src/asf/m5_shared/metrics/collector.py: CallMetric, ToolMetric, LimitEvent, MetricsSnapshot
#   - called by src/asf/m5_shared/metrics/advisories.py: MetricsSnapshot, ResourceAdvisory
#   - called by src/asf/m4_execution/scheduler.py: ResourceAdvisory
#   - called by src/asf/cli/views/dash_view.py: MetricsSnapshot
#   - called by tests/contracts/test_metrics.py: ValueSource, CallMetric, ToolMetric, LimitEvent, MetricsSnapshot, ResourceAdvisory
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
# DONE WHEN: (1) tests/contracts/test_metrics.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/contracts/metrics.py` and `uv run mypy src/asf/contracts/metrics.py` are clean.

from enum import StrEnum

from pydantic import BaseModel, Field

from asf.contracts.ids import RunId, TaskId


class ValueSource(StrEnum):
    MEASURED = "MEASURED"
    ESTIMATED = "ESTIMATED"


class CallMetric(BaseModel):
    run_id: RunId
    task_id: TaskId | None
    role: str
    provider: str
    model: str
    strategy: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost: float
    source: ValueSource
    retry_no: int = 0


class ToolMetric(BaseModel):
    run_id: RunId
    task_id: TaskId | None
    tool: str
    strategy: str = Field(description="tool_loop | code_exec | ... (D-19 comparability)")
    duration_ms: int
    exit_status: str
    approval: str
    sandbox_tier: str


class LimitEvent(BaseModel):
    run_id: RunId
    kind: str = Field(description="budget | quota | rate_limit | vram | retry_storm")
    detail: str


class MetricsSnapshot(BaseModel):
    """IF-19."""
    run_id: RunId | None
    values: dict[str, float]
    sources: dict[str, ValueSource]
    advisories: list[str] = Field(default_factory=list)


class ResourceAdvisory(BaseModel):
    """IF-20."""
    kind: str
    severity: str = Field(description="soft | hard")
    max_slots: int | None = None
    detail: str
