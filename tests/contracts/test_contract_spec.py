# FILE: tests/contracts/test_contract_spec.py
# ROLE: Tests that prove src/asf/contracts/contract_spec.py meets its DONE WHEN conditions.
# ARCH REF: p09 Registry; p15 ContractSpec; IF-07 ContractRegister; IF-08 ContractQuery; A-1; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/contract_spec.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/contract_spec.py: ContractStatus, Operation, ContractSpec, ContractCapsule, ContractQuery (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_contract_spec.py` on Windows and Linux once src/asf/contracts/contract_spec.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_contract_spec.py` and `uv run mypy tests/contracts/test_contract_spec.py` are clean.


from typing import Any

import pytest
from pydantic import ValidationError

from asf.contracts.contract_spec import ContractCapsule, ContractQuery, ContractSpec, ContractStatus, Operation


def _operation() -> dict[str, Any]:
    return {"name": "put", "signature": "put(data: bytes) -> str", "returns": "sha256 ref", "example": "put(b'x')"}


def _spec() -> dict[str, Any]:
    return {"contract_id": "c_1", "module_id": "blobs", "version": "1.0.0", "operations": [_operation()]}


def test_status_values_match_the_lifecycle() -> None:
    assert [s.value for s in ContractStatus] == ["DRAFT", "VERIFIED", "STABLE", "DEPRECATED"]


def test_operation_defaults_and_required_fields() -> None:
    op = Operation.model_validate(_operation())
    assert op.params == {}
    assert op.errors == []
    for missing in ("name", "signature", "returns", "example"):
        data = _operation()
        del data[missing]
        with pytest.raises(ValidationError):
            Operation.model_validate(data)


def test_spec_defaults_to_draft_with_empty_collections() -> None:
    spec = ContractSpec.model_validate(_spec())
    assert spec.status is ContractStatus.DRAFT
    assert spec.data_schemas == {}
    assert spec.invariants == []
    assert spec.producer_task is None
    assert spec.consumer_tasks == []
    assert spec.contract_test_refs == []


def test_spec_requires_operations() -> None:
    data = _spec()
    del data["operations"]
    with pytest.raises(ValidationError):
        ContractSpec.model_validate(data)


def test_spec_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        ContractSpec.model_validate({**_spec(), "status": "FINAL"})


def test_spec_json_round_trip_with_tasks_and_status() -> None:
    spec = ContractSpec.model_validate({**_spec(), "status": "STABLE", "producer_task": "t1", "consumer_tasks": ["t2", "t3"]})
    assert ContractSpec.model_validate_json(spec.model_dump_json()) == spec


@pytest.mark.parametrize("count", [3, 4, 5])
def test_capsule_accepts_three_to_five_lines(count: int) -> None:
    capsule = ContractCapsule.model_validate({"module_id": "m", "version": "1", "operation": "op", "lines": ["x"] * count})
    assert len(capsule.lines) == count


@pytest.mark.parametrize("count", [0, 2, 6])
def test_capsule_rejects_fewer_than_three_or_more_than_five_lines(count: int) -> None:
    with pytest.raises(ValidationError):
        ContractCapsule.model_validate({"module_id": "m", "version": "1", "operation": "op", "lines": ["x"] * count})


def test_query_is_valid_with_no_arguments_and_lists_are_independent() -> None:
    a = ContractQuery()
    b = ContractQuery()
    assert a.module_ids == [] and a.task_id is None and a.pinned_versions == {}
    a.module_ids.append("blobs")
    assert b.module_ids == []
