# FILE: tests/m3_orchestration/decomposition/test_sizer.py
# ROLE: Tests that prove src/asf/m3_orchestration/decomposition/sizer.py meets its DONE WHEN conditions.
# ARCH REF: M3; p05 sizing; p06 leaf-sizing model; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/decomposition/sizer.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/decomposition/sizer.py: FIT_FRACTION, estimate_size, fits_leaf (unit under test)
#   - imports from src/asf/contracts/models.py: ModelProfile (profile fixtures)
#   - imports from src/asf/contracts/tasks.py: TaskNode (node fixtures)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/decomposition/test_sizer.py` on Windows and Linux once src/asf/m3_orchestration/decomposition/sizer.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/decomposition/test_sizer.py` and `uv run mypy tests/m3_orchestration/decomposition/test_sizer.py` are clean.

import pytest

from asf.contracts.models import ModelProfile
from asf.contracts.tasks import TaskNode
from asf.m3_orchestration.decomposition.sizer import FIT_FRACTION, estimate_size, fits_leaf


def _node(**over: object) -> TaskNode:
    base = {"id": "t1", "run_id": "r1", "kind": "composite", "goal": "write the refund module", "idempotency_key": "k"}
    return TaskNode.model_validate({**base, **over})


def _profile(c_eff: int = 10_000) -> ModelProfile:
    return ModelProfile.model_validate({"model_id": "m", "backend": "llama-server", "c_eff_tokens": c_eff, "max_slots": 1, "tokens_per_s": 30.0})


def test_the_estimate_is_deterministic_and_grows_with_context_and_criteria() -> None:
    node = _node()
    assert estimate_size(node, 1000) == estimate_size(node, 1000)
    assert estimate_size(node, 2000) == estimate_size(node, 1000) + 1000
    more = _node(acceptance_refs=["a", "b", "c"], contract_refs=["x@1"])
    assert estimate_size(more, 1000) > estimate_size(node, 1000)


def test_a_node_with_no_criteria_or_contracts_still_costs_at_least_one_function() -> None:
    assert estimate_size(_node(), 0) >= 150


def test_negative_context_is_treated_as_zero() -> None:
    assert estimate_size(_node(), -500) == estimate_size(_node(), 0)


def test_fits_when_everything_is_inside_the_limits() -> None:
    node = _node(allowed_files=["a.py", "b.py", "c.py"], contract_refs=["w@1", "x@1", "y@1", "z@1"])
    assert fits_leaf(node, int(FIT_FRACTION * 10_000), _profile())


@pytest.mark.parametrize(
    "over",
    [{"allowed_files": ["a", "b", "c", "d"]}, {"contract_refs": ["1@1", "2@1", "3@1", "4@1", "5@1"]}],
)
def test_too_many_files_or_interfaces_do_not_fit(over: dict[str, list[str]]) -> None:
    assert not fits_leaf(_node(**over), 100, _profile())


def test_too_many_tokens_do_not_fit() -> None:
    assert not fits_leaf(_node(), int(FIT_FRACTION * 10_000) + 1, _profile())
    assert fits_leaf(_node(), 100, _profile(c_eff=1000)) and not fits_leaf(_node(), 700, _profile(c_eff=1000))


def test_the_rubric_risk_can_veto_a_leaf() -> None:
    assert fits_leaf(_node(), 100, _profile(), risk=0.5)
    assert not fits_leaf(_node(), 100, _profile(), risk=0.9)
    assert fits_leaf(_node(), 100, _profile(), risk=0.9, max_risk=0.95)


def test_limits_can_be_overridden() -> None:
    node = _node(allowed_files=["a", "b", "c", "d"])
    assert fits_leaf(node, 100, _profile(), max_files=4)
