# FILE: tests/contracts/test_errors.py
# ROLE: Tests that prove src/asf/contracts/errors.py meets its DONE WHEN conditions.
# ARCH REF: p16 failure matrix; all modules; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/errors.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/errors.py: AsfError, ConfigError, PolicyDenied, ApprovalRequired, BudgetExceeded, ContextOverflow, ProviderUnavailable, InvalidModelOutput, SandboxUnavailable, StateConflict, NotSupportedOnPlatform (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_errors.py` on Windows and Linux once src/asf/contracts/errors.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_errors.py` and `uv run mypy tests/contracts/test_errors.py` are clean.


from asf.contracts.errors import (  # noqa: F401
    ApprovalRequired,
    AsfError,
    BudgetExceeded,
    ConfigError,
    ContextOverflow,
    InvalidModelOutput,
    NotSupportedOnPlatform,
    PolicyDenied,
    ProviderUnavailable,
    SandboxUnavailable,
    StateConflict,
)


def test_asf_error_meets_contract() -> None:
    """Prove AsfError behaves as declared in src/asf/contracts/errors.py."""
    raise NotImplementedError("write this test before implementing AsfError")

def test_config_error_meets_contract() -> None:
    """Prove ConfigError behaves as declared in src/asf/contracts/errors.py."""
    raise NotImplementedError("write this test before implementing ConfigError")

def test_policy_denied_meets_contract() -> None:
    """Prove PolicyDenied behaves as declared in src/asf/contracts/errors.py."""
    raise NotImplementedError("write this test before implementing PolicyDenied")

def test_approval_required_meets_contract() -> None:
    """Prove ApprovalRequired behaves as declared in src/asf/contracts/errors.py."""
    raise NotImplementedError("write this test before implementing ApprovalRequired")

def test_budget_exceeded_meets_contract() -> None:
    """Prove BudgetExceeded behaves as declared in src/asf/contracts/errors.py."""
    raise NotImplementedError("write this test before implementing BudgetExceeded")

def test_context_overflow_meets_contract() -> None:
    """Prove ContextOverflow behaves as declared in src/asf/contracts/errors.py."""
    raise NotImplementedError("write this test before implementing ContextOverflow")

def test_provider_unavailable_meets_contract() -> None:
    """Prove ProviderUnavailable behaves as declared in src/asf/contracts/errors.py."""
    raise NotImplementedError("write this test before implementing ProviderUnavailable")

def test_invalid_model_output_meets_contract() -> None:
    """Prove InvalidModelOutput behaves as declared in src/asf/contracts/errors.py."""
    raise NotImplementedError("write this test before implementing InvalidModelOutput")

def test_sandbox_unavailable_meets_contract() -> None:
    """Prove SandboxUnavailable behaves as declared in src/asf/contracts/errors.py."""
    raise NotImplementedError("write this test before implementing SandboxUnavailable")

def test_state_conflict_meets_contract() -> None:
    """Prove StateConflict behaves as declared in src/asf/contracts/errors.py."""
    raise NotImplementedError("write this test before implementing StateConflict")

def test_not_supported_on_platform_meets_contract() -> None:
    """Prove NotSupportedOnPlatform behaves as declared in src/asf/contracts/errors.py."""
    raise NotImplementedError("write this test before implementing NotSupportedOnPlatform")
