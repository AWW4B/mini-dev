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



import pytest

from asf.contracts.errors import (
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

SUBCLASSES = [
    ConfigError,
    PolicyDenied,
    ApprovalRequired,
    BudgetExceeded,
    ContextOverflow,
    ProviderUnavailable,
    InvalidModelOutput,
    SandboxUnavailable,
    StateConflict,
    NotSupportedOnPlatform,
]


def test_base_error_is_an_exception() -> None:
    assert issubclass(AsfError, Exception)


@pytest.mark.parametrize("cls", SUBCLASSES)
def test_every_error_derives_directly_from_asf_error(cls: type[AsfError]) -> None:
    assert cls.__bases__ == (AsfError,)


@pytest.mark.parametrize("cls", SUBCLASSES)
def test_every_error_is_caught_by_the_base_class_and_keeps_its_message(cls: type[AsfError]) -> None:
    with pytest.raises(AsfError) as info:
        raise cls("something actionable happened")
    assert type(info.value) is cls
    assert str(info.value) == "something actionable happened"


@pytest.mark.parametrize("cls", SUBCLASSES)
def test_every_error_has_a_docstring_saying_when_it_is_raised(cls: type[AsfError]) -> None:
    assert cls.__doc__ is not None and cls.__doc__.strip()


def test_errors_are_distinct_types_and_not_interchangeable() -> None:
    assert len(set(SUBCLASSES)) == len(SUBCLASSES)
    with pytest.raises(PolicyDenied):
        try:
            raise PolicyDenied("no")
        except ConfigError:
            pytest.fail("PolicyDenied must not be caught as ConfigError")
