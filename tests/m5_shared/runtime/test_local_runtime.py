# FILE: tests/m5_shared/runtime/test_local_runtime.py
# ROLE: Tests that prove src/asf/m5_shared/runtime/local_runtime.py meets its DONE WHEN conditions.
# ARCH REF: M5; p11 Local Runtime; IF-13 SlotLease; D-08 (tiny model may run on CPU); D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/runtime/local_runtime.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/runtime/local_runtime.py: LocalRuntime (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/runtime/test_local_runtime.py` on Windows and Linux once src/asf/m5_shared/runtime/local_runtime.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/runtime/test_local_runtime.py` and `uv run mypy tests/m5_shared/runtime/test_local_runtime.py` are clean.


import time
from types import SimpleNamespace
from typing import Any

import pytest

from asf.m5_shared.runtime.local_runtime import LocalRuntime


class FakeBackend:
    name = "fake"

    def start(self, model_id: str, ctx_tokens: int, slots: int) -> str:
        return "http://127.0.0.1:8080/v1"

    def stop(self) -> None:
        pass

    def healthy(self) -> bool:
        return True


class FakeProbe:
    def __init__(self, vram_free_mb: int | None = 8192) -> None:
        self.vram_free_mb = vram_free_mb

    def read(self) -> Any:
        return SimpleNamespace(
            ram_free_mb=16384,
            vram_free_mb=self.vram_free_mb,
            gpu_util_pct=10.0,
            measured={"ram": True, "vram": True, "gpu_util": True},
        )


def test_local_runtime_meets_contract() -> None:
    """Prove LocalRuntime behaves as declared in src/asf/m5_shared/runtime/local_runtime.py."""
    backend = FakeBackend()
    probe = FakeProbe()
    runtime = LocalRuntime(backend=backend, probe=probe, max_slots=1)  # type: ignore[arg-type]

    assert runtime.max_slots() == 1

    req = SimpleNamespace(
        model_id="qwen-coder",
        ctx_tokens=4096,
        ttl_s=300,
        priority=0,
    )

    # 1. Acquire lease
    lease1 = runtime.acquire(req)  # type: ignore[arg-type]
    assert lease1 is not None
    assert lease1.model_id == "qwen-coder"
    assert lease1.ctx_tokens == 4096
    assert lease1.expires_at_monotonic > time.monotonic()
    assert lease1.base_url == "http://127.0.0.1:8080/v1"

    # 2. Acquire when full returns None
    lease2 = runtime.acquire(req)  # type: ignore[arg-type]
    assert lease2 is None

    # 3. Heartbeat extends expiry
    old_expiry = lease1.expires_at_monotonic
    runtime.heartbeat(lease1.lease_id)
    assert runtime._active_leases[lease1.lease_id].expires_at_monotonic >= old_expiry

    # Heartbeat on invalid lease raises
    with pytest.raises(Exception, match="not found"):
        runtime.heartbeat("invalid-lease")

    # 4. Release frees slot
    runtime.release(lease1.lease_id)
    lease3 = runtime.acquire(req)  # type: ignore[arg-type]
    assert lease3 is not None

    # 5. Drop stale
    lease3.expires_at_monotonic = time.monotonic() - 10.0
    dropped = runtime.drop_stale()
    assert dropped == 1
    assert len(runtime._active_leases) == 0

    # 6. Reject when insufficient VRAM
    low_vram_probe = FakeProbe(vram_free_mb=100)
    low_vram_runtime = LocalRuntime(backend=backend, probe=low_vram_probe, max_slots=1)  # type: ignore[arg-type]
    with pytest.raises(Exception, match="RESOURCE_UNAVAILABLE"):
        low_vram_runtime.acquire(req)  # type: ignore[arg-type]
