# FILE: tests/contracts/test_models.py
# ROLE: Tests that prove src/asf/contracts/models.py meets its DONE WHEN conditions.
# ARCH REF: p11; IF-12; IF-13; IF-20 ModelProfile; D-07; D-08; D-09; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/models.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/models.py: ModelRole, InferenceRequest, InferenceResult, SlotLeaseRequest, SlotLease, ModelProfile (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_models.py` on Windows and Linux once src/asf/contracts/models.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_models.py` and `uv run mypy tests/contracts/test_models.py` are clean.


from typing import Any

import pytest
from pydantic import ValidationError

from asf.contracts.models import InferenceRequest, InferenceResult, ModelProfile, ModelRole, SlotLease, SlotLeaseRequest


def test_model_roles() -> None:
    assert [r.value for r in ModelRole] == ["T1", "T2", "T3", "reviewer"]


def test_inference_request_defaults() -> None:
    req = InferenceRequest.model_validate({"role": "T2", "purpose": "code_step", "budget_key": "run1"})
    assert req.role is ModelRole.T2
    assert req.max_output_tokens == 2048
    assert req.output_schema is None
    assert req.lease_id is None


def test_inference_request_rejects_unknown_role_and_requires_budget_key() -> None:
    with pytest.raises(ValidationError):
        InferenceRequest.model_validate({"role": "T9", "purpose": "p", "budget_key": "b"})
    with pytest.raises(ValidationError):
        InferenceRequest.model_validate({"role": "T1", "purpose": "p"})


def test_inference_result_allows_unknown_cost_but_requires_the_flag() -> None:
    base = {"provider": "p", "model": "m", "content": {"a": 1}, "tokens_in": 1, "tokens_out": 2, "latency_ms": 3}
    assert InferenceResult.model_validate({**base, "cost": None, "cost_estimated": True}).cost is None
    with pytest.raises(ValidationError):
        InferenceResult.model_validate({**base, "cost": 0.1})


def test_slot_lease_request_defaults() -> None:
    req = SlotLeaseRequest.model_validate({"model_id": "m", "ctx_tokens": 8192})
    assert req.ttl_s == 600
    assert req.priority == 0


def test_slot_lease_round_trip() -> None:
    lease = SlotLease.model_validate(
        {"lease_id": "l1", "model_id": "m", "ctx_tokens": 8192, "expires_at_monotonic": 12.5, "base_url": "http://127.0.0.1:8080/v1"}
    )
    assert SlotLease.model_validate_json(lease.model_dump_json()) == lease


def _profile(**over: Any) -> dict[str, Any]:
    return {"model_id": "m", "backend": "llama-server", "c_eff_tokens": 8000, "max_slots": 1, "tokens_per_s": 30.0, **over}


@pytest.mark.parametrize("slots", [1, 2])
def test_profile_accepts_one_or_two_slots(slots: int) -> None:
    assert ModelProfile.model_validate(_profile(max_slots=slots)).max_slots == slots


@pytest.mark.parametrize("slots", [0, 3, -1])
def test_profile_rejects_other_slot_counts(slots: int) -> None:
    with pytest.raises(ValidationError):
        ModelProfile.model_validate(_profile(max_slots=slots))


def test_profile_vram_table_keys_survive_json() -> None:
    profile = ModelProfile.model_validate(_profile(vram_mb_by_ctx={4096: 5000, 8192: 6200}, success_by_size_bucket={"S": 0.9}))
    again = ModelProfile.model_validate_json(profile.model_dump_json())
    assert again.vram_mb_by_ctx == {4096: 5000, 8192: 6200}
    assert again == profile
