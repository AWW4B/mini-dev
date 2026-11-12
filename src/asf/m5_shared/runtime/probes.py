# FILE: src/asf/m5_shared/runtime/probes.py
# ROLE: Reads RAM, VRAM and GPU utilisation, marking each value MEASURED or ESTIMATED.
# ARCH REF: M5; p10 probe; p11; D-45
# OWNS: Resource readings
# DOES NOT OWN: Deciding thresholds
# CONNECTS TO (external boundaries only):
#   - called by src/asf/m5_shared/runtime/local_runtime.py: ResourceProbe
#   - called by src/asf/m5_shared/runtime/calibration.py: ResourceProbe
#   - called by src/asf/doctor/checks.py: ResourceProbe
#   - called by tests/m5_shared/runtime/test_probes.py: ResourceReading, ResourceProbe
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Use psutil for RAM and nvidia-ml-py (NVML) for GPU; if NVML is unavailable return ESTIMATED/None values instead of raising.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/runtime/test_probes.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/runtime/probes.py` and `uv run mypy src/asf/m5_shared/runtime/probes.py` are clean.

import logging

import psutil
import pynvml  # type: ignore[import-untyped]
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ResourceReading(BaseModel):
    ram_free_mb: int
    vram_free_mb: int | None
    gpu_util_pct: float | None
    measured: dict[str, bool]


class ResourceProbe:
    def read(self) -> ResourceReading:
        ram_free_mb = int(psutil.virtual_memory().available / (1024 * 1024))
        measured = {"ram": True, "vram": False, "gpu_util": False}
        vram_free_mb: int | None = None
        gpu_util_pct: float | None = None

        try:
            pynvml.nvmlInit()
            try:
                device_count = pynvml.nvmlDeviceGetCount()
                if device_count > 0:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    vram_free_mb = int(mem_info.free / (1024 * 1024))
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    gpu_util_pct = float(util.gpu)
                    measured["vram"] = True
                    measured["gpu_util"] = True
            finally:
                try:
                    pynvml.nvmlShutdown()
                except Exception:  # noqa: BLE001 - NVML shutdown errors are not actionable
                    logger.debug("nvmlShutdown failed", exc_info=True)
        except Exception:  # noqa: BLE001 - no NVIDIA GPU or driver is the normal case: readings are flagged unmeasured
            logger.debug("GPU probe unavailable; VRAM and utilisation are not measured", exc_info=True)

        return ResourceReading(
            ram_free_mb=ram_free_mb,
            vram_free_mb=vram_free_mb,
            gpu_util_pct=gpu_util_pct,
            measured=measured,
        )
