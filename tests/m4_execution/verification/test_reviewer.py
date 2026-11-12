# FILE: tests/m4_execution/verification/test_reviewer.py
# ROLE: Tests that prove src/asf/m4_execution/verification/reviewer.py meets its DONE WHEN conditions.
# ARCH REF: M4; p08 reviewer; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m4_execution/verification/reviewer.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m4_execution/verification/reviewer.py: review_change (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m4_execution/verification/test_reviewer.py` on Windows and Linux once src/asf/m4_execution/verification/reviewer.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m4_execution/verification/test_reviewer.py` and `uv run mypy tests/m4_execution/verification/test_reviewer.py` are clean.

from types import SimpleNamespace
from typing import Any

from asf.m4_execution.verification.reviewer import review_change

CHANGE = SimpleNamespace(files_touched=["src/billing.py"], self_report="added charge()")


class _Gateway:
    def __init__(self, answer: str | Exception) -> None:
        self.answer = answer
        self.prompts: list[str] = []
        self.roles: list[Any] = []

    def model_for(self, role: Any, purpose: str, **_: Any) -> Any:
        self.roles.append(role)
        outer = self

        class _Model:
            def invoke(self, prompt: str) -> Any:
                outer.prompts.append(prompt)
                if isinstance(outer.answer, Exception):
                    raise outer.answer
                return SimpleNamespace(content=outer.answer)

        return _Model()


def test_without_a_gateway_the_review_is_skipped() -> None:
    assert review_change(CHANGE, ["charge(amount) -> Receipt"]) == []  # type: ignore[arg-type]


def test_only_blocking_findings_are_returned() -> None:
    answer = (
        'Here you go: [{"blocking": true, "finding": "charge() returns None, the contract says Receipt"},'
        ' {"blocking": false, "finding": "naming"}, {"blocking": true, "finding": "  "}]'
    )
    gateway = _Gateway(answer)
    findings = review_change(CHANGE, ["charge(amount) -> Receipt"], gateway=gateway, diff_text="+def charge(): pass")  # type: ignore[arg-type]
    assert findings == ["charge() returns None, the contract says Receipt"]
    assert gateway.roles == ["reviewer"]
    assert "charge(amount) -> Receipt" in gateway.prompts[0] and "+def charge(): pass" in gateway.prompts[0]


def test_garbage_or_failing_model_output_yields_no_findings() -> None:
    assert review_change(CHANGE, [], gateway=_Gateway("looks fine to me"))  == []  # type: ignore[arg-type]
    assert review_change(CHANGE, [], gateway=_Gateway("[not json"))  == []  # type: ignore[arg-type]
    assert review_change(CHANGE, [], gateway=_Gateway(RuntimeError("budget exceeded"))) == []  # type: ignore[arg-type]


def test_a_huge_diff_is_truncated_in_the_prompt() -> None:
    gateway = _Gateway("[]")
    review_change(CHANGE, [], gateway=gateway, diff_text="x" * 100_000)  # type: ignore[arg-type]
    assert len(gateway.prompts[0]) < 20_000
