# FILE: tests/m5_shared/memory/test_budgets.py
# ROLE: Tests for src/asf/m5_shared/memory/budgets.py.
# ARCH REF: M5; p12 Context & Memory Service; docs/architecture/MEMORY_ARCHITECTURE.md
# OWNS: Tests of budgets
# DOES NOT OWN: Production code
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/memory/budgets.py: budgets_for, layer_shares, LAYERS (unit under test)
#   - imports from src/asf/m5_shared/memory/device_budget.py: load_memory_config (packaged config)
#   - imports from src/asf/contracts/errors.py: ConfigError (invalid shares)
#   - imports from tests/conftest.py: fake_paths (isolated app directories)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/memory/test_budgets.py` on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/memory/test_budgets.py` and `uv run mypy tests/m5_shared/memory/test_budgets.py` are clean.

from typing import Any

import pytest

from asf.contracts.errors import ConfigError
from asf.m5_shared.memory.budgets import LAYERS, budgets_for, layer_shares
from asf.m5_shared.memory.device_budget import load_memory_config


@pytest.fixture
def config(fake_paths: Any) -> dict[str, Any]:
    _ = fake_paths
    return load_memory_config()


@pytest.mark.parametrize("role", ["T1", "T2", "T3", "reviewer"])
def test_every_packaged_role_table_covers_all_layers_and_sums_to_the_window(config: dict[str, Any], role: str) -> None:
    assert set(layer_shares(config, role)) == set(LAYERS)
    for window in (4096, 16384, 131072):
        b = budgets_for(role, window, config)
        assert sum(b.get(layer) for layer in LAYERS) == window
        assert b.input_tokens == window - b.output and b.output > 0


def test_budgets_scale_with_the_window_not_fixed_numbers(config: dict[str, Any]) -> None:
    small, large = budgets_for("T2", 8192, config), budgets_for("T2", 32768, config)
    assert large.working == pytest.approx(small.working * 4, abs=4)
    assert budgets_for("T1", 8192, config).memory_tokens == 0  # the tiny model gets no history


def test_a_table_that_does_not_sum_to_100_is_rejected(config: dict[str, Any]) -> None:
    broken = {"layers": {"T2": {**config["layers"]["T2"], "working": 50}}}
    with pytest.raises(ConfigError, match="sums to"):
        budgets_for("T2", 8192, broken)
    with pytest.raises(ConfigError, match="no \\[layers.nobody\\]"):
        budgets_for("nobody", 8192, config)
    with pytest.raises(ConfigError, match="positive"):
        budgets_for("T2", 0, config)
    with pytest.raises(ConfigError, match="unknown memory layer"):
        budgets_for("T2", 8192, config).get("dreams")
