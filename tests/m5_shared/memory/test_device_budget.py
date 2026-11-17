# FILE: tests/m5_shared/memory/test_device_budget.py
# ROLE: Tests for src/asf/m5_shared/memory/device_budget.py.
# ARCH REF: M5; p12 Context & Memory Service; docs/architecture/MEMORY_ARCHITECTURE.md
# OWNS: Tests of device_budget
# DOES NOT OWN: Production code
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/memory/device_budget.py: DeviceSnapshot, plan_device, probe_device, load_memory_config, model_mb, pct (unit under test)
#   - imports from src/asf/contracts/errors.py: ConfigError (invalid percentages)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/memory/test_device_budget.py` on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/memory/test_device_budget.py` and `uv run mypy tests/m5_shared/memory/test_device_budget.py` are clean.

from pathlib import Path
from typing import Any

import pytest

from asf.contracts.errors import ConfigError
from asf.m5_shared.memory.device_budget import DeviceSnapshot, load_memory_config, model_mb, pct, plan_device, probe_device


def _laptop(ram_free: int = 10_000, vram_free: int | None = 5_900) -> DeviceSnapshot:
    """The development machine: 15.2 GB RAM, RTX 4050 6 GB, 6 cores / 12 threads."""
    return DeviceSnapshot(
        ram_total_mb=15_565, ram_free_mb=ram_free, cpu_physical=6, cpu_logical=12, disk_free_mb=210_000,
        vram_total_mb=6_141 if vram_free is not None else None, vram_free_mb=vram_free, gpu_name="RTX 4050" if vram_free else None,
    )


@pytest.fixture
def config(fake_paths: Any) -> dict[str, Any]:
    _ = fake_paths
    return load_memory_config()


def test_the_shares_never_exceed_their_percentage_of_the_device(config: dict[str, Any]) -> None:
    snap = _laptop()
    plan = plan_device(snap, config)
    device = config["device"]
    assert plan.ram_cap_mb <= snap.ram_total_mb * pct(device, "total_ram_pct") and plan.ram_cap_mb <= snap.ram_free_mb * pct(device, "total_ram_free_pct")
    assert plan.process_ram_mb + plan.models_ram_mb <= plan.ram_cap_mb
    assert plan.vram_cap_mb <= snap.vram_total_mb * pct(device, "vram_pct")  # type: ignore[operator]
    assert plan.cpu_threads <= snap.cpu_logical * pct(device, "cpu_threads_pct") and plan.worker_threads >= 1
    used_vram = sum(m.gpu_mb for m in plan.models.values())
    used_ram = sum(m.ram_mb for m in plan.models.values())
    assert used_vram <= plan.vram_cap_mb and used_ram <= plan.models_ram_mb
    assert plan.disk_cap_mb == int(snap.disk_free_mb * pct(device, "disk_free_pct"))


def test_on_this_laptop_the_7b_coder_runs_on_the_gpu_and_the_tiny_model_on_the_cpu(config: dict[str, Any]) -> None:
    plan = plan_device(_laptop(), config)
    assert plan.models["T1"].placement == "cpu" and plan.models["T1"].name.startswith("Qwen3-1.7B")
    t2 = plan.models["T2"]
    assert t2.name == "Qwen2.5-Coder-7B-Instruct-Q4_K_M" and t2.context_tokens >= 8192
    assert t2.gpu_fraction >= pct(config["device"], "min_gpu_fraction_pct")
    assert any("14B" in w for w in plan.warnings)  # the stronger model is named with what it would need
    assert plan.window_tokens("T2") == t2.context_tokens and plan.window_tokens("T3") == plan.remote_window_tokens


def test_little_free_ram_shrinks_the_plan_instead_of_taking_the_machine(config: dict[str, Any]) -> None:
    roomy = plan_device(_laptop(ram_free=10_000), config)
    tight = plan_device(_laptop(ram_free=1_500), config)
    assert tight.ram_cap_mb < roomy.ram_cap_mb
    assert sum(m.ram_mb for m in tight.models.values()) <= tight.models_ram_mb
    assert any("free" in w for w in tight.warnings)


def test_without_a_gpu_models_are_planned_for_the_cpu_or_routed_away(config: dict[str, Any]) -> None:
    plan = plan_device(_laptop(vram_free=None), config)
    assert plan.vram_cap_mb == 0
    assert all(m.gpu_mb == 0 for m in plan.models.values())
    assert "T2" in plan.models or any("remote" in w for w in plan.warnings)


def test_model_size_grows_with_context_and_halves_its_cache_at_q8(config: dict[str, Any]) -> None:
    entry = {"weights_gb": 1.0, "kv_bytes_per_token": 100_000}
    device = dict(config["device"])
    assert model_mb(entry, 16384, device) > model_mb(entry, 4096, device)
    fp16 = model_mb(entry, 16384, {**device, "kv_cache_bytes_pct": 100})
    assert fp16 > model_mb(entry, 16384, device)


@pytest.mark.parametrize("bad", [-1, 101, "50", True])
def test_a_limit_that_is_not_a_percentage_is_a_configuration_error(bad: object) -> None:
    with pytest.raises(ConfigError, match="percentage"):
        pct({"x": bad}, "x")
    with pytest.raises(ConfigError, match="missing"):
        pct({}, "x")


def test_the_probe_measures_this_machine(tmp_path: Path) -> None:
    snap = probe_device(tmp_path / "does" / "not" / "exist")
    assert snap.ram_total_mb > 0 and 0 < snap.ram_free_mb <= snap.ram_total_mb
    assert snap.cpu_logical >= snap.cpu_physical >= 1 and snap.disk_free_mb > 0
    assert (snap.vram_total_mb is None) == (snap.vram_free_mb is None)
