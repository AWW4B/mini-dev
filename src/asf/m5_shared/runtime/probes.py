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

from pydantic import BaseModel


class ResourceReading(BaseModel):
    ram_free_mb: int
    vram_free_mb: int | None
    gpu_util_pct: float | None
    measured: dict[str, bool]


class ResourceProbe:
    def read(self) -> ResourceReading:
        raise NotImplementedError
