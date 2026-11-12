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
#   - called by src/asf/m3_orchestration/run_graph.py: LocalRuntime
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

import time
import uuid

from asf.contracts.errors import AsfError
from asf.contracts.models import SlotLease, SlotLeaseRequest
from asf.m5_shared.runtime.backends import LocalRuntimeBackend
from asf.m5_shared.runtime.probes import ResourceProbe


class LocalRuntime:
    backend: LocalRuntimeBackend | None
    probe: ResourceProbe
    _max_slots: int
    _active_leases: dict[str, SlotLease]

    def __init__(
        self,
        backend: LocalRuntimeBackend | None = None,
        probe: ResourceProbe | None = None,
        max_slots: int = 1,
    ) -> None:
        self.backend = backend
        self.probe = probe or ResourceProbe()
        self._max_slots = max(1, min(2, max_slots))
        self._active_leases = {}

    def max_slots(self) -> int:
        return self._max_slots

    def acquire(self, request: SlotLeaseRequest) -> SlotLease | None:
        """Return a lease, or None when no slot is free (caller waits for SLOT_FREE)."""
        self.drop_stale()

        if len(self._active_leases) >= self._max_slots:
            return None

        # Check resources (reject rather than overcommit VRAM)
        reading = self.probe.read()
        if reading.vram_free_mb is not None and reading.vram_free_mb < 500:
            raise AsfError(f"RESOURCE_UNAVAILABLE: insufficient VRAM ({reading.vram_free_mb} MB free)")

        base_url = "http://127.0.0.1:8080/v1"
        if self.backend is not None:
            base_url = self.backend.start(request.model_id, request.ctx_tokens, self._max_slots)

        lease_id = f"lease_{uuid.uuid4().hex[:12]}"
        now = time.monotonic()
        expires_at = now + float(request.ttl_s)

        lease = SlotLease(
            lease_id=lease_id,  # type: ignore[arg-type]
            model_id=request.model_id,
            ctx_tokens=request.ctx_tokens,
            expires_at_monotonic=expires_at,
            base_url=base_url,
        )
        self._active_leases[lease_id] = lease
        return lease

    def heartbeat(self, lease_id: str) -> None:
        if lease_id not in self._active_leases:
            raise AsfError(f"Lease '{lease_id}' not found or already expired")

        lease = self._active_leases[lease_id]
        new_expiry = time.monotonic() + 600.0
        # Update expires_at_monotonic on the lease
        updated_lease = SlotLease(
            lease_id=lease.lease_id,
            model_id=lease.model_id,
            ctx_tokens=lease.ctx_tokens,
            expires_at_monotonic=new_expiry,
            base_url=lease.base_url,
        )
        self._active_leases[lease_id] = updated_lease

    def release(self, lease_id: str) -> None:
        if lease_id in self._active_leases:
            del self._active_leases[lease_id]

    def drop_stale(self) -> int:
        now = time.monotonic()
        stale_ids = [lid for lid, lease in self._active_leases.items() if lease.expires_at_monotonic <= now]
        for lid in stale_ids:
            del self._active_leases[lid]
        return len(stale_ids)
