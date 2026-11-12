# FILE: tests/m4_execution/integration/test_repair.py
# ROLE: Tests that prove src/asf/m4_execution/integration/repair.py meets its DONE WHEN conditions.
# ARCH REF: M4; p08 repair; p06 REPAIRING; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m4_execution/integration/repair.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m4_execution/integration/repair.py: make_repair_task (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m4_execution/integration/test_repair.py` on Windows and Linux once src/asf/m4_execution/integration/repair.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m4_execution/integration/test_repair.py` and `uv run mypy tests/m4_execution/integration/test_repair.py` are clean.

from typing import Any

import pytest

from asf.m4_execution.integration.repair import make_repair_task


class _Parent:
    """Duck-typed TaskNode: the repair only reads these attributes."""

    def __init__(self, **over: Any) -> None:
        self.id = "p1"
        self.run_id = "r1"
        self.goal = "integrate the billing module"
        self.contract_refs = ["billing@1.0.0"]
        self.allowed_files = ["src/billing.py"]
        self.priority = 3
        self.depth = 2
        self.__dict__.update(over)


def test_first_failure_creates_a_scoped_repair_leaf() -> None:
    node = make_repair_task(_Parent(), "sha256:abc", 0)  # type: ignore[arg-type]
    assert node is not None
    assert node.kind.value == "repair"
    assert node.parent_id == "p1" and node.run_id == "r1"
    assert node.acceptance_refs == ["sha256:abc"]
    assert node.allowed_files == ["src/billing.py"]
    assert node.contract_refs == ["billing@1.0.0"]
    assert node.priority == 4 and node.depth == 3
    assert node.state.value == "PROPOSED"
    assert node.counters.repair_rounds == 1
    assert "billing" in node.goal and "sha256:abc" in node.goal


def test_ids_and_idempotency_keys_are_deterministic_per_round() -> None:
    first = make_repair_task(_Parent(), "sha256:abc", 0)  # type: ignore[arg-type]
    again = make_repair_task(_Parent(), "sha256:abc", 0)  # type: ignore[arg-type]
    second = make_repair_task(_Parent(), "sha256:def", 1)  # type: ignore[arg-type]
    assert first is not None and again is not None and second is not None
    assert first.id == again.id and first.idempotency_key == again.idempotency_key
    assert second.id != first.id and second.idempotency_key != first.idempotency_key


def test_repair_rounds_are_bounded() -> None:
    assert make_repair_task(_Parent(), "sha256:abc", 2) is None  # type: ignore[arg-type]
    assert make_repair_task(_Parent(), "sha256:abc", 7) is None  # type: ignore[arg-type]


def test_negative_round_is_a_programming_error() -> None:
    with pytest.raises(ValueError):
        make_repair_task(_Parent(), "sha256:abc", -1)  # type: ignore[arg-type]


def test_repair_does_not_share_lists_with_the_parent() -> None:
    parent = _Parent()
    node = make_repair_task(parent, "sha256:abc", 0)  # type: ignore[arg-type]
    assert node is not None
    node.allowed_files.append("src/other.py")
    assert parent.allowed_files == ["src/billing.py"]
