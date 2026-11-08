# FILE: src/asf/m5_shared/runtime/local_runtime.py
# ROLE: Grants and reclaims inference-slot leases and manages model residency for 1-3 configured local models.
# ARCH REF: M5; p11 Local Runtime; IF-13 SlotLease; D-08 (tiny model may run on CPU)
# OWNS: Slots, leases, residency, eviction
# DOES NOT OWN: Task selection (scheduler)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/models.py: SlotLease, SlotLeaseRequest (IF-13)
#   - imports from src/asf/m5_shared/runtime/backends.py: LocalRuntimeBackend (servers)
#   - imports from src/asf/m5_shared/runtime/probes.py: ResourceProbe (VRAM/RAM)
#   - imports from src/asf/contracts/errors.py: AsfError (error types)
#   - called by src/asf/m5_shared/state_store/recovery.py: LocalRuntime
#   - called by src/asf/m3_orchestration/run_control.py: LocalRuntime
#   - called by src/asf/m4_execution/scheduler.py: LocalRuntime
#   - called by tests/m5_shared/runtime/test_local_runtime.py: LocalRuntime
#   - emits/consumes: emits SLOT_FREE events (consumed by the scheduler)
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. max_slots comes from the calibrated ModelProfile (1 default, 2 only if calibration allows).
#   6. Reject with RESOURCE_UNAVAILABLE rather than overcommitting VRAM.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/runtime/test_local_runtime.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/runtime/local_runtime.py` and `uv run mypy src/asf/m5_shared/runtime/local_runtime.py` are clean.

from asf.contracts.models import SlotLease, SlotLeaseRequest


class LocalRuntime:
    def acquire(self, request: SlotLeaseRequest) -> SlotLease | None:
        """Return a lease, or None when no slot is free (caller waits for SLOT_FREE)."""
        raise NotImplementedError

    def heartbeat(self, lease_id: str) -> None:
        raise NotImplementedError

    def release(self, lease_id: str) -> None:
        raise NotImplementedError

    def drop_stale(self) -> int:
        raise NotImplementedError

    def max_slots(self) -> int:
        raise NotImplementedError
