# FILE: tests/m5_shared/context/test_context_service.py
# ROLE: Tests that prove src/asf/m5_shared/context/context_service.py meets its DONE WHEN conditions.
# ARCH REF: M5; p12 Context & Memory Service; IF-11 ContextRequest/ContextPack; IF-08 (capsules); A-1; D-31; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/context/context_service.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/context/context_service.py: ContextService (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/context/test_context_service.py` on Windows and Linux once src/asf/m5_shared/context/context_service.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/context/test_context_service.py` and `uv run mypy tests/m5_shared/context/test_context_service.py` are clean.

from types import SimpleNamespace
from typing import Any

import pytest

from asf.m5_shared.context.context_service import ContextService


def test_context_service_meets_contract() -> None:
    """Prove ContextService behaves as declared in src/asf/m5_shared/context/context_service.py."""
    svc = ContextService()

    # Add items across tiers (0: P0_SPEC, 1: P1_CAPSULES, 2: P2_ALLOWED_FILES, 3: P3_SNIPPETS)
    item_p0 = SimpleNamespace(
        tier=0,
        source_ref="task:t1",
        sha256="abc",
        tokens=20,
        text="Task specification content",
    )
    item_p1 = SimpleNamespace(
        tier=1,
        source_ref="capsule:auth",
        sha256="def",
        tokens=30,
        text="Interface contract capsule for auth",
    )
    item_p2 = SimpleNamespace(
        tier=2,
        source_ref="file:src/auth.py",
        sha256="123",
        tokens=40,
        text="Allowed file source code",
    )
    item_p3 = SimpleNamespace(
        tier=3,
        source_ref="snippet:utils",
        sha256="456",
        tokens=50,
        text="Code snippet from repo index",
    )

    svc.add_item(item_p0)  # type: ignore[arg-type]
    svc.add_item(item_p1)  # type: ignore[arg-type]
    svc.add_item(item_p2)  # type: ignore[arg-type]
    svc.add_item(item_p3)  # type: ignore[arg-type]

    # 1. Budget of 100 fits must-haves (P0+P1+P2 = 90 tokens)
    req: Any = SimpleNamespace(
        task_id="task_001",
        role="T3",
        budget_tokens=100,
        model_id="gpt-4o",
    )
    assert svc.dry_run_fits(req) is True

    pack = svc.build(req)
    assert pack.task_id == "task_001"
    assert pack.role == "T3"
    assert pack.token_count <= 100
    # Must-haves must all be included
    tiers = [int(it.tier) for it in pack.items]
    assert 0 in tiers
    assert 1 in tiers
    assert 2 in tiers
    # P3 snippet (50 tokens) did not fit (90 + 50 > 100)
    assert 3 not in tiers

    # 2. Budget with enough room includes P3 as well
    req_large: Any = SimpleNamespace(
        task_id="task_001",
        role="T3",
        budget_tokens=200,
        model_id="gpt-4o",
    )
    pack_large = svc.build(req_large)
    assert pack_large.token_count <= 200
    tiers_large = [int(it.tier) for it in pack_large.items]
    assert 3 in tiers_large

    # 3. Budget below must-haves raises ContextOverflow
    req_small: Any = SimpleNamespace(
        task_id="task_001",
        role="T3",
        budget_tokens=80,  # 90 needed
        model_id="gpt-4o",
    )
    assert svc.dry_run_fits(req_small) is False

    with pytest.raises(Exception, match="Must-have context"):
        svc.build(req_small)
