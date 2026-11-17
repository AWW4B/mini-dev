# FILE: src/asf/m5_shared/memory/device_budget.py
# ROLE: Measures RAM, VRAM, CPU and disk and turns memory.toml percentages into this machine's limits and local model sizes.
# ARCH REF: M5; p12 Context & Memory Service; docs/architecture/MEMORY_ARCHITECTURE.md
# OWNS: Device snapshot, percentage shares, local model placement and context size
# DOES NOT OWN: Running the model servers (runtime/backends.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/loader.py: load_layered (memory.toml)
#   - imports from src/asf/config/paths.py: get_paths (data directory for the disk probe)
#   - imports from src/asf/contracts/errors.py: ConfigError (invalid percentages)
#   - called by tests/m5_shared/memory/test_device_budget.py: DeviceSnapshot, plan_device, probe_device, load_memory_config, model_mb, pct
#   - called by src/asf/m5_shared/memory/budgets.py: pct
#   - called by src/asf/m5_shared/memory/store.py: pct
#   - called by src/asf/m5_shared/memory/tool_outputs.py: pct
#   - called by src/asf/m5_shared/memory/router.py: pct
#   - called by src/asf/m4_execution/worker/strategies.py: load_memory_config
#   - called by tests/m5_shared/memory/test_budgets.py: load_memory_config
#   - called by tests/m5_shared/memory/test_router.py: load_memory_config
#   - called by tests/m5_shared/memory/test_tool_outputs.py: load_memory_config
#   - called by src/asf/m5_shared/memory/hooks.py: DevicePlan, load_memory_config, plan_device, probe_device
#   - called by tests/m5_shared/memory/test_hooks.py: DeviceSnapshot, load_memory_config, plan_device
#   - called by src/asf/cli/commands/memory_cmd.py: load_memory_config, plan_device, probe_device
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/memory/test_device_budget.py pass on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/memory/device_budget.py` and `uv run mypy src/asf/m5_shared/memory/device_budget.py` are clean.

import logging
import math
import os
import shutil
from pathlib import Path
from typing import Any, Literal

import psutil
from pydantic import BaseModel, Field

from asf.config.loader import load_layered
from asf.config.paths import get_paths
from asf.contracts.errors import ConfigError

logger = logging.getLogger(__name__)

_MB = 1024 * 1024
Placement = Literal["gpu", "cpu", "split"]


class DeviceSnapshot(BaseModel):
    """What the machine has, measured now. VRAM fields are None without an NVIDIA GPU (or without its driver)."""

    ram_total_mb: int
    ram_free_mb: int
    cpu_physical: int
    cpu_logical: int
    disk_free_mb: int
    vram_total_mb: int | None = None
    vram_free_mb: int | None = None
    gpu_name: str | None = None


class ModelFit(BaseModel):
    role: str
    name: str
    placement: Placement
    context_tokens: int
    gpu_mb: int
    ram_mb: int
    gpu_fraction: float
    threads: int


class DevicePlan(BaseModel):
    """Every resource limit of mini-dev on this machine, derived from percentages of the snapshot."""

    snapshot: DeviceSnapshot
    ram_cap_mb: int
    process_ram_mb: int
    models_ram_mb: int
    sqlite_cache_mb: int
    vram_cap_mb: int
    cpu_threads: int
    worker_threads: int
    disk_cap_mb: int
    models: dict[str, ModelFit] = Field(default_factory=dict)
    remote_window_tokens: int = 131072
    warnings: list[str] = Field(default_factory=list)

    def window_tokens(self, role: str) -> int:
        """The usable context window of the model serving ``role``: a sized local model, or the remote provider's window."""
        fit = self.models.get(role)
        return fit.context_tokens if fit is not None else self.remote_window_tokens


def load_memory_config(project_root: Path | None = None) -> dict[str, Any]:
    """memory.toml merged across the package, user and project layers."""
    return load_layered("memory", project_root=project_root)


def pct(config: dict[str, Any], key: str) -> float:
    """A percentage from the config as a fraction in [0, 1]; anything else is a configuration error."""
    if key not in config:
        raise ConfigError(f"memory.toml is missing '{key}'. Restore it from the packaged defaults.")
    value = config[key]
    if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value <= 100:
        raise ConfigError(f"memory.toml '{key}' must be a percentage between 0 and 100, got {value!r}.")
    return float(value) / 100.0


def _gpu() -> tuple[int | None, int | None, str | None]:
    try:
        import pynvml  # type: ignore[import-untyped]

        pynvml.nvmlInit()
    except Exception:  # noqa: BLE001 - no NVIDIA GPU or driver is the normal case: VRAM is reported as unmeasured
        logger.debug("no NVIDIA GPU visible; planning for CPU only", exc_info=True)
        return None, None, None
    try:
        if pynvml.nvmlDeviceGetCount() < 1:
            return None, None, None
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
        name = pynvml.nvmlDeviceGetName(handle)
        return int(memory.total // _MB), int(memory.free // _MB), name.decode() if isinstance(name, bytes) else str(name)
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:  # noqa: BLE001 - shutdown errors are not actionable
            logger.debug("nvmlShutdown failed", exc_info=True)


def probe_device(data_dir: Path | None = None) -> DeviceSnapshot:
    """Measure RAM, CPU, the disk holding the data directory and (when present) the first NVIDIA GPU."""
    memory = psutil.virtual_memory()
    target = data_dir or get_paths().data_dir
    probe_at = target
    while not probe_at.exists() and probe_at.parent != probe_at:
        probe_at = probe_at.parent
    vram_total, vram_free, gpu_name = _gpu()
    return DeviceSnapshot(
        ram_total_mb=int(memory.total // _MB),
        ram_free_mb=int(memory.available // _MB),
        cpu_physical=psutil.cpu_count(logical=False) or 1,
        cpu_logical=psutil.cpu_count(logical=True) or os.cpu_count() or 1,
        disk_free_mb=int(shutil.disk_usage(probe_at).free // _MB),
        vram_total_mb=vram_total,
        vram_free_mb=vram_free,
        gpu_name=gpu_name,
    )


def model_mb(entry: dict[str, Any], context_tokens: int, device: dict[str, Any]) -> int:
    """Weights + KV cache for ``context_tokens`` + runtime overhead, in MB."""
    weights = float(entry["weights_gb"]) * 1024
    kv = float(entry["kv_bytes_per_token"]) * pct(device, "kv_cache_bytes_pct") * context_tokens / _MB
    return math.ceil((weights + kv) * (1 + pct(device, "runtime_overhead_pct")))


def _candidates(catalog: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    return sorted((e for e in catalog if role in e.get("roles", [])), key=lambda e: -int(e.get("quality", 0)))


def _contexts(device: dict[str, Any], entry: dict[str, Any], ceiling: int | None = None) -> list[int]:
    limit = min(int(entry.get("max_context", 0)) or 1 << 30, ceiling or 1 << 30)
    return sorted((int(c) for c in device.get("context_candidates", [4096, 8192]) if int(c) <= limit), reverse=True)


def _fit_cpu(entry: dict[str, Any], device: dict[str, Any], ram_left: int, threads: int, role: str, ceiling: int) -> ModelFit | None:
    for ctx in _contexts(device, entry, ceiling):
        need = model_mb(entry, ctx, device)
        if need <= ram_left:
            return ModelFit(role=role, name=str(entry["name"]), placement="cpu", context_tokens=ctx, gpu_mb=0, ram_mb=need, gpu_fraction=0.0, threads=threads)
    return None


def _fit_gpu(entry: dict[str, Any], device: dict[str, Any], vram_left: int, ram_left: int, threads: int, role: str, min_ctx: int) -> ModelFit | None:
    for ctx in _contexts(device, entry):
        if ctx < min_ctx:
            break
        need = model_mb(entry, ctx, device)
        on_gpu = min(need, vram_left)
        spill = need - on_gpu
        fraction = on_gpu / need if need else 0.0
        if on_gpu > 0 and fraction >= pct(device, "min_gpu_fraction_pct") and spill <= ram_left:
            return ModelFit(
                role=role, name=str(entry["name"]), placement="gpu" if spill == 0 else "split", context_tokens=ctx,
                gpu_mb=on_gpu, ram_mb=spill, gpu_fraction=round(fraction, 3), threads=threads,
            )
    return None


def plan_device(snapshot: DeviceSnapshot, config: dict[str, Any]) -> DevicePlan:
    """Turn the percentage shares of memory.toml into absolute limits for this machine and size the local models.

    Each share is the smaller of a share of the device total and a share of what is free now. T1 (tiny) is placed on
    the CPU first, then the strongest T2 coder whose context reaches 8k is placed on the GPU, spilling to RAM only while
    ``min_gpu_fraction_pct`` of it stays on the GPU. What does not fit is reported in ``warnings``; nothing is silently
    shrunk below a usable size.
    """
    device = dict(config.get("device", {}))
    catalog: list[dict[str, Any]] = list(device.get("catalog", []))
    ram_cap = int(min(snapshot.ram_total_mb * pct(device, "total_ram_pct"), snapshot.ram_free_mb * pct(device, "total_ram_free_pct")))
    process_ram = int(ram_cap * pct(device, "process_ram_pct"))
    models_ram = int(ram_cap * pct(device, "models_ram_pct"))
    vram_cap = 0
    if snapshot.vram_total_mb is not None and snapshot.vram_free_mb is not None:
        vram_cap = int(min(snapshot.vram_total_mb * pct(device, "vram_pct"), snapshot.vram_free_mb * pct(device, "vram_free_pct")))
    cpu_threads = max(1, math.floor(snapshot.cpu_logical * pct(device, "cpu_threads_pct")))
    model_threads = max(1, min(snapshot.cpu_physical, cpu_threads // 2))
    plan = DevicePlan(
        snapshot=snapshot, ram_cap_mb=ram_cap, process_ram_mb=process_ram, models_ram_mb=models_ram,
        sqlite_cache_mb=max(1, int(process_ram * pct(device, "sqlite_cache_pct"))), vram_cap_mb=vram_cap, cpu_threads=cpu_threads,
        worker_threads=max(1, cpu_threads - model_threads), disk_cap_mb=int(snapshot.disk_free_mb * pct(device, "disk_free_pct")),
        remote_window_tokens=int(config.get("remote", {}).get("window_tokens", 131072)),
    )
    ram_left = models_ram

    tiny = sorted((e for e in catalog if "T1" in e.get("roles", []) and e.get("placement") == "cpu"), key=lambda e: float(e["weights_gb"]))
    for entry in tiny:  # the smallest CPU model: T1 does narrow jobs and must never compete with the coder for VRAM
        fit = _fit_cpu(entry, device, ram_left, model_threads, "T1", ceiling=8192)
        if fit is not None:
            plan.models["T1"] = fit
            ram_left -= fit.ram_mb
            break
    else:
        plan.warnings.append(f"No tiny model fits in {ram_left} MB of RAM; T1 tasks fall back to deterministic code.")

    t2: ModelFit | None = None
    if vram_cap > 0:
        for min_ctx in (8192, 4096):  # prefer a stronger model with a usable window over a bigger window on a weaker model
            for entry in _candidates(catalog, "T2"):
                t2 = _fit_gpu(entry, device, vram_cap, ram_left, model_threads, "T2", min_ctx)
                if t2 is not None:
                    break
            if t2 is not None:
                break
    else:
        for entry in _candidates(catalog, "T2"):
            t2 = _fit_cpu(entry, device, ram_left, model_threads, "T2", ceiling=8192)
            if t2 is not None:
                break
    if t2 is None:
        plan.warnings.append("No local coder fits inside the shares; route T2 to a remote provider (profile api-heavy).")
    else:
        plan.models["T2"] = t2
        ram_left -= t2.ram_mb
        stronger = [e for e in _candidates(catalog, "T2") if int(e.get("quality", 0)) > next(int(c.get("quality", 0)) for c in catalog if c["name"] == t2.name)]
        if stronger:
            want = model_mb(stronger[-1], 16384, device)
            plan.warnings.append(
                f"{stronger[-1]['name']} at 16k context needs about {want} MB; it does not fit the current shares "
                f"(VRAM share {vram_cap} MB, RAM left for models {max(0, ram_left)} MB). Freeing RAM or VRAM may allow it."
            )
    if snapshot.ram_free_mb < snapshot.ram_total_mb * 0.25:
        plan.warnings.append(f"Only {snapshot.ram_free_mb} MB of {snapshot.ram_total_mb} MB RAM is free; the shares were reduced to match.")
    return plan
