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


from asf.contracts.models import InferenceRequest, InferenceResult, ModelProfile, ModelRole, SlotLease, SlotLeaseRequest  # noqa: F401


def test_model_role_meets_contract() -> None:
    """Prove ModelRole behaves as declared in src/asf/contracts/models.py."""
    raise NotImplementedError("write this test before implementing ModelRole")

def test_inference_request_meets_contract() -> None:
    """Prove InferenceRequest behaves as declared in src/asf/contracts/models.py."""
    raise NotImplementedError("write this test before implementing InferenceRequest")

def test_inference_result_meets_contract() -> None:
    """Prove InferenceResult behaves as declared in src/asf/contracts/models.py."""
    raise NotImplementedError("write this test before implementing InferenceResult")

def test_slot_lease_request_meets_contract() -> None:
    """Prove SlotLeaseRequest behaves as declared in src/asf/contracts/models.py."""
    raise NotImplementedError("write this test before implementing SlotLeaseRequest")

def test_slot_lease_meets_contract() -> None:
    """Prove SlotLease behaves as declared in src/asf/contracts/models.py."""
    raise NotImplementedError("write this test before implementing SlotLease")

def test_model_profile_meets_contract() -> None:
    """Prove ModelProfile behaves as declared in src/asf/contracts/models.py."""
    raise NotImplementedError("write this test before implementing ModelProfile")
