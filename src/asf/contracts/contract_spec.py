# FILE: src/asf/contracts/contract_spec.py
# ROLE: Defines module contracts (IF-07) and the pinned 3-5 line contract capsule (A-1) returned by IF-08.
# ARCH REF: p09 Registry; p15 ContractSpec; IF-07 ContractRegister; IF-08 ContractQuery; A-1
# OWNS: Contract and capsule shapes, IF-07/IF-08 request models
# DOES NOT OWN: Compatibility rules (src/asf/m5_shared/registry/compatibility.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/ids.py: ContractId, TaskId (typed ids)
#   - called by src/asf/contracts/tasks.py: ContractCapsule
#   - called by src/asf/m5_shared/registry/compatibility.py: ContractSpec
#   - called by src/asf/m5_shared/registry/capsules.py: ContractSpec, ContractCapsule
#   - called by src/asf/m5_shared/registry/registry.py: ContractSpec, ContractCapsule, ContractQuery, ContractStatus
#   - called by tests/contracts/test_contract_spec.py: ContractStatus, Operation, ContractSpec, ContractCapsule, ContractQuery
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. This file is declarations only: Pydantic models, enums and type aliases. Add field validators only where the docstring of a field states a constraint.
#   6. Every model must round-trip through model_dump_json() / model_validate_json() unchanged; the JSON Schema exported from these models is the published contract (D-39: no hand-written JSON).
#   7. Changing a field name or type is a contract change: stop and report instead.
#   8. ContractCapsule.lines must hold 3 to 5 lines: signature, parameter meanings, returns, errors, one example (A-1).
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; business logic; I/O; imports from asf.m1-m5 packages, asf.cli, asf.web or asf.platform
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/contracts/test_contract_spec.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/contracts/contract_spec.py` and `uv run mypy src/asf/contracts/contract_spec.py` are clean.

from enum import StrEnum

from pydantic import BaseModel, Field

from asf.contracts.ids import ContractId, TaskId


class ContractStatus(StrEnum):
    DRAFT = "DRAFT"
    VERIFIED = "VERIFIED"
    STABLE = "STABLE"
    DEPRECATED = "DEPRECATED"


class Operation(BaseModel):
    name: str
    signature: str
    params: dict[str, str] = Field(default_factory=dict, description="param name -> meaning")
    returns: str
    errors: list[str] = Field(default_factory=list)
    example: str


class ContractSpec(BaseModel):
    """IF-07 ContractRegister payload. Declared top-down by the planner (A-1)."""
    contract_id: ContractId
    module_id: str
    version: str = Field(description="semver")
    status: ContractStatus = ContractStatus.DRAFT
    operations: list[Operation]
    data_schemas: dict[str, str] = Field(default_factory=dict)
    invariants: list[str] = Field(default_factory=list)
    producer_task: TaskId | None = None
    consumer_tasks: list[TaskId] = Field(default_factory=list)
    contract_test_refs: list[str] = Field(default_factory=list)


class ContractCapsule(BaseModel):
    """A-1: what a worker sees of a dependency. Never the implementation."""
    module_id: str
    version: str
    operation: str
    lines: list[str] = Field(min_length=3, max_length=5)


class ContractQuery(BaseModel):
    """IF-08 request."""
    module_ids: list[str] = Field(default_factory=list)
    task_id: TaskId | None = None
    pinned_versions: dict[str, str] = Field(default_factory=dict)
