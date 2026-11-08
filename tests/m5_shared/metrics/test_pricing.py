# FILE: tests/m5_shared/metrics/test_pricing.py
# ROLE: Tests that prove src/asf/m5_shared/metrics/pricing.py meets its DONE WHEN conditions.
# ARCH REF: M5; p10; D-27; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/metrics/pricing.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/metrics/pricing.py: price_for (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/metrics/test_pricing.py` on Windows and Linux once src/asf/m5_shared/metrics/pricing.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/metrics/test_pricing.py` and `uv run mypy tests/m5_shared/metrics/test_pricing.py` are clean.

import pytest

from asf.m5_shared.metrics.pricing import price_for


def test_price_for_meets_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prove price_for behaves as declared in src/asf/m5_shared/metrics/pricing.py."""
    # 1. Missing entries return 0.0 with estimated=True
    cost, est = price_for("unknown_provider", "unknown_model", 1000, 2000)
    assert cost == 0.0
    assert est is True

    # 2. Known pricing table
    fake_pricing = {
        "anthropic": {
            "claude-3-5-sonnet": {
                "input_per_mtok": 3.0,
                "output_per_mtok": 15.0,
            },
            "incomplete_model": {
                "input_per_mtok": 3.0,
            },
        },
        "currency": "USD",
    }
    monkeypatch.setattr(
        "asf.m5_shared.metrics.pricing.load_layered",
        lambda _filename: fake_pricing,
    )

    cost, est = price_for("anthropic", "claude-3-5-sonnet", 1_000_000, 1_000_000)
    assert cost == 18.0
    assert est is False

    cost2, est2 = price_for("anthropic", "claude-3-5-sonnet", 500_000, 100_000)
    assert abs(cost2 - 3.0) < 1e-6
    assert est2 is False

    # Incomplete pricing entry
    cost_inc, est_inc = price_for("anthropic", "incomplete_model", 1000, 1000)
    assert cost_inc == 0.0
    assert est_inc is True
