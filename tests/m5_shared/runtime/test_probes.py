# FILE: tests/m5_shared/runtime/test_probes.py
# ROLE: Tests that prove src/asf/m5_shared/runtime/probes.py meets its DONE WHEN conditions.
# ARCH REF: M5; p10 probe; p11; D-45; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/runtime/probes.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/runtime/probes.py: ResourceReading, ResourceProbe (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/runtime/test_probes.py` on Windows and Linux once src/asf/m5_shared/runtime/probes.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/runtime/test_probes.py` and `uv run mypy tests/m5_shared/runtime/test_probes.py` are clean.


from types import SimpleNamespace
from typing import Any

import pytest

from asf.m5_shared.runtime.probes import ResourceProbe, ResourceReading


def test_resource_reading_meets_contract() -> None:
    """Prove ResourceReading behaves as declared in src/asf/m5_shared/runtime/probes.py."""
    reading = ResourceReading(
        ram_free_mb=8192,
        vram_free_mb=4096,
        gpu_util_pct=15.5,
        measured={"ram": True, "vram": True, "gpu_util": True},
    )
    assert reading.ram_free_mb == 8192
    assert reading.vram_free_mb == 4096
    assert reading.gpu_util_pct == 15.5
    assert reading.measured["ram"] is True

    dumped = reading.model_dump()
    loaded = ResourceReading.model_validate(dumped)
    assert loaded == reading

    # Without GPU
    no_gpu = ResourceReading(
        ram_free_mb=4096,
        vram_free_mb=None,
        gpu_util_pct=None,
        measured={"ram": True, "vram": False, "gpu_util": False},
    )
    assert no_gpu.vram_free_mb is None
    assert no_gpu.gpu_util_pct is None
    assert no_gpu.measured["vram"] is False


def test_resource_probe_meets_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prove ResourceProbe behaves as declared in src/asf/m5_shared/runtime/probes.py."""
    probe = ResourceProbe()

    # 1. Unmocked read succeeds and gives positive RAM
    reading = probe.read()
    assert reading.ram_free_mb > 0
    assert reading.measured.get("ram") is True
    assert "vram" in reading.measured
    assert "gpu_util" in reading.measured

    # 2. When NVML is unavailable / fails to init
    class FailingNvml:
        @staticmethod
        def nvmlInit() -> None:
            raise RuntimeError("NVML unavailable")

    monkeypatch.setattr("asf.m5_shared.runtime.probes.pynvml", FailingNvml)
    reading_no_gpu = probe.read()
    assert reading_no_gpu.ram_free_mb > 0
    assert reading_no_gpu.vram_free_mb is None
    assert reading_no_gpu.gpu_util_pct is None
    assert reading_no_gpu.measured["vram"] is False
    assert reading_no_gpu.measured["gpu_util"] is False

    # 3. When NVML succeeds
    class FakeNvml:
        @staticmethod
        def nvmlInit() -> None:
            pass

        @staticmethod
        def nvmlShutdown() -> None:
            pass

        @staticmethod
        def nvmlDeviceGetCount() -> int:
            return 1

        @staticmethod
        def nvmlDeviceGetHandleByIndex(idx: int) -> Any:
            return "handle-0"

        @staticmethod
        def nvmlDeviceGetMemoryInfo(handle: Any) -> Any:
            return SimpleNamespace(free=8 * 1024 * 1024 * 1024)  # 8192 MB

        @staticmethod
        def nvmlDeviceGetUtilizationRates(handle: Any) -> Any:
            return SimpleNamespace(gpu=42)

    monkeypatch.setattr("asf.m5_shared.runtime.probes.pynvml", FakeNvml)
    reading_gpu = probe.read()
    assert reading_gpu.vram_free_mb == 8192
    assert reading_gpu.gpu_util_pct == 42.0
    assert reading_gpu.measured["vram"] is True
    assert reading_gpu.measured["gpu_util"] is True
