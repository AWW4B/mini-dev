# FILE: tests/contracts/test_context.py
# ROLE: Tests that prove src/asf/contracts/context.py meets its DONE WHEN conditions.
# ARCH REF: p12 Context & Memory Service; p15 ContextPack; IF-11; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/context.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/context.py: ContextTier, ContextRequest, ContextItem, ContextPack (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_context.py` on Windows and Linux once src/asf/contracts/context.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_context.py` and `uv run mypy tests/contracts/test_context.py` are clean.


from typing import Any

import pytest
from pydantic import ValidationError

from asf.contracts.context import ContextItem, ContextPack, ContextRequest, ContextTier


def _item(tier: int = 0) -> dict[str, Any]:
    return {"tier": tier, "source_ref": "spec#1", "sha256": "ab" * 32, "tokens": 12, "text": "hello"}


def _pack(items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "pack_id": "pack_1",
        "task_id": "task_1",
        "role": "worker",
        "budget_tokens": 4000,
        "token_count": 12,
        "items": items if items is not None else [_item()],
    }


def test_tiers_are_ordered_from_spec_to_failure() -> None:
    assert [int(t) for t in ContextTier] == [0, 1, 2, 3, 4, 5]
    assert ContextTier.P0_SPEC < ContextTier.P1_CAPSULES < ContextTier.P5_FAILURE
    assert ContextTier(2) is ContextTier.P2_ALLOWED_FILES


def test_request_requires_budget_and_model() -> None:
    req = ContextRequest.model_validate({"task_id": "t", "role": "worker", "budget_tokens": 100, "model_id": "m"})
    assert req.budget_tokens == 100
    with pytest.raises(ValidationError):
        ContextRequest.model_validate({"task_id": "t", "role": "worker", "budget_tokens": 100})


def test_item_converts_int_tier_and_rejects_unknown_tier() -> None:
    assert ContextItem.model_validate(_item(3)).tier is ContextTier.P3_SNIPPETS
    with pytest.raises(ValidationError):
        ContextItem.model_validate(_item(9))


def test_pack_defaults_report_nothing_dropped_and_measured_tokens() -> None:
    pack = ContextPack.model_validate(_pack())
    assert pack.dropped == []
    assert pack.token_count_estimated is False


def test_pack_default_lists_are_not_shared_between_instances() -> None:
    a = ContextPack.model_validate(_pack())
    b = ContextPack.model_validate(_pack())
    a.dropped.append("p3:snippet")
    assert b.dropped == []


def test_pack_rejects_a_malformed_item() -> None:
    bad = _item()
    del bad["text"]
    with pytest.raises(ValidationError):
        ContextPack.model_validate(_pack([bad]))


def test_pack_json_round_trip_keeps_tier_enum() -> None:
    pack = ContextPack.model_validate(_pack([_item(0), _item(4)]))
    again = ContextPack.model_validate_json(pack.model_dump_json())
    assert again == pack
    assert again.items[1].tier is ContextTier.P4_DECISIONS
