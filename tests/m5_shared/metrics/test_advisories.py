# FILE: tests/m5_shared/metrics/test_advisories.py
# ROLE: Tests that prove src/asf/m5_shared/metrics/advisories.py meets its DONE WHEN conditions.
# ARCH REF: M5; p10; IF-20 ResourceAdvisory; p06 budgets; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/metrics/advisories.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/metrics/advisories.py: evaluate_thresholds (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/metrics/test_advisories.py` on Windows and Linux once src/asf/m5_shared/metrics/advisories.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/metrics/test_advisories.py` and `uv run mypy tests/m5_shared/metrics/test_advisories.py` are clean.

from types import SimpleNamespace

from asf.m5_shared.metrics.advisories import evaluate_thresholds


def test_evaluate_thresholds_meets_contract() -> None:
    """Prove evaluate_thresholds behaves as declared in src/asf/m5_shared/metrics/advisories.py."""
    budget = SimpleNamespace(
        max_api_spend=10.0,
        max_remote_tokens=100_000,
        max_task_nodes=50,
        used_remote_tokens=0,
        used_task_nodes=0,
        alert_fraction=0.8,
    )

    # 1. Normal usage below 80% produces no advisories
    normal_snap = SimpleNamespace(
        values={"cost": 1.0, "input_tokens": 1000.0, "output_tokens": 500.0, "task_nodes": 5.0}
    )
    advisories = evaluate_thresholds(normal_snap, budget)  # type: ignore[arg-type]
    assert len(advisories) == 0

    # 2. Soft alert when spend reaches alert_fraction (>= 80% and < 100%)
    soft_spend_snap = SimpleNamespace(
        values={"cost": 8.5, "input_tokens": 1000.0, "output_tokens": 500.0, "task_nodes": 5.0}
    )
    soft_advisories = evaluate_thresholds(soft_spend_snap, budget)  # type: ignore[arg-type]
    assert len(soft_advisories) == 1
    assert soft_advisories[0].kind == "budget_spend"
    assert soft_advisories[0].severity == "soft"

    # 3. Hard limit when spend reaches or exceeds 100%
    hard_spend_snap = SimpleNamespace(
        values={"cost": 10.5, "input_tokens": 1000.0, "output_tokens": 500.0, "task_nodes": 5.0}
    )
    hard_advisories = evaluate_thresholds(hard_spend_snap, budget)  # type: ignore[arg-type]
    assert len(hard_advisories) == 1
    assert hard_advisories[0].kind == "budget_spend"
    assert hard_advisories[0].severity == "hard"
    assert hard_advisories[0].max_slots == 0

    # 4. Token limit exceeded triggers hard token advisory
    token_snap = SimpleNamespace(
        values={"cost": 1.0, "input_tokens": 80_000.0, "output_tokens": 25_000.0, "task_nodes": 5.0}
    )
    token_advisories = evaluate_thresholds(token_snap, budget)  # type: ignore[arg-type]
    assert any(a.kind == "budget_tokens" and a.severity == "hard" for a in token_advisories)
