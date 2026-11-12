# FILE: tests/m4_execution/verification/test_failure_classifier.py
# ROLE: Tests that prove src/asf/m4_execution/verification/failure_classifier.py meets its DONE WHEN conditions.
# ARCH REF: M4; p08 classify failure; D-09 tiny-model tasks; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m4_execution/verification/failure_classifier.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m4_execution/verification/failure_classifier.py: classify_failure (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m4_execution/verification/test_failure_classifier.py` on Windows and Linux once src/asf/m4_execution/verification/failure_classifier.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m4_execution/verification/test_failure_classifier.py` and `uv run mypy tests/m4_execution/verification/test_failure_classifier.py` are clean.

from types import SimpleNamespace
from typing import Any

import pytest

from asf.m4_execution.verification.failure_classifier import classify_failure


@pytest.mark.parametrize(
    ("log", "expected"),
    [
        ("E   AssertionError: assert 1 == 2\nFAILED tests/test_x.py::test_a", "LOCAL_BUG"),
        ("PolicyDenied: path outside allowed_files", "POLICY_VIOLATION"),
        ("openai.BadRequestError: maximum context length is 8192 tokens", "CONTEXT_OVERFLOW"),
        ("the step budget was exhausted before the tests passed", "SPEC_TOO_LARGE"),
        ("OSError: [Errno 28] No space left on device", "ENV_INFRA"),
        ("httpx.ConnectError: Connection refused", "ENV_INFRA"),
        ("'uv' is not recognized as an internal or external command", "ENV_INFRA"),
        ("TypeError: charge() got an unexpected keyword argument 'currency'", "CONTRACT_MISMATCH"),
        ("FAILED tests/contracts/test_billing_contract.py::test_signature", "CONTRACT_MISMATCH"),
        ("tests/test_net.py::test_fetch flaky: timed out waiting for the server", "FLAKY"),
    ],
)
def test_rules_classify_known_failures(log: str, expected: str) -> None:
    assert classify_failure(log).value == expected


def test_earlier_rules_beat_later_ones() -> None:
    log = "PolicyDenied while the Connection refused message was also logged"
    assert classify_failure(log).value == "POLICY_VIOLATION"


class _Gateway:
    def __init__(self, answer: str | Exception) -> None:
        self.answer = answer
        self.calls: list[tuple[Any, str]] = []

    def model_for(self, role: Any, purpose: str, **_: Any) -> Any:
        self.calls.append((role, purpose))
        outer = self

        class _Model:
            def invoke(self, _prompt: str) -> Any:
                if isinstance(outer.answer, Exception):
                    raise outer.answer
                return SimpleNamespace(content=outer.answer)

        return _Model()


def test_the_tiny_model_is_asked_only_when_no_rule_matches() -> None:
    gateway = _Gateway("FLAKY")
    assert classify_failure("something odd happened", gateway=gateway).value == "FLAKY"  # type: ignore[arg-type]
    assert gateway.calls == [("T1", "classify_failure")]


def test_the_model_is_not_called_when_a_rule_matches() -> None:
    gateway = _Gateway("FLAKY")
    assert classify_failure("Connection refused", gateway=gateway).value == "ENV_INFRA"  # type: ignore[arg-type]
    assert gateway.calls == []


def test_an_unparseable_or_failing_model_falls_back_to_local_bug() -> None:
    assert classify_failure("odd", gateway=_Gateway("no idea"), ).value == "LOCAL_BUG"  # type: ignore[arg-type]
    assert classify_failure("odd", gateway=_Gateway(RuntimeError("provider down"))).value == "LOCAL_BUG"  # type: ignore[arg-type]


def test_an_empty_log_defaults_to_local_bug_without_calling_the_model() -> None:
    gateway = _Gateway("FLAKY")
    assert classify_failure("   ", gateway=gateway).value == "LOCAL_BUG"  # type: ignore[arg-type]
    assert gateway.calls == []
