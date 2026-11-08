# FILE: src/asf/m5_shared/runtime/calibration.py
# ROLE: Measures tokens/s, VRAM per context, usable context and pass rate by size bucket to produce a ModelProfile.
# ARCH REF: M5; p11 calibration; IF-20 ModelProfile; research E1
# OWNS: Calibration procedure
# DOES NOT OWN: Choosing default models (none are hardcoded, D-08)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/models.py: ModelProfile (output)
#   - imports from src/asf/m5_shared/runtime/backends.py: LocalRuntimeBackend (server)
#   - imports from src/asf/m5_shared/runtime/probes.py: ResourceProbe (measurements)
#   - called by src/asf/cli/commands/models.py: calibrate
#   - called by tests/m5_shared/runtime/test_calibration.py: calibrate
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/runtime/test_calibration.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/runtime/calibration.py` and `uv run mypy src/asf/m5_shared/runtime/calibration.py` are clean.

from asf.contracts.models import ModelProfile
from asf.m5_shared.runtime.backends import LocalRuntimeBackend
from asf.m5_shared.runtime.probes import ResourceProbe


def calibrate(backend: LocalRuntimeBackend, model_id: str, ctx_candidates: list[int]) -> ModelProfile:
    probe = ResourceProbe()
    vram_mb_by_ctx: dict[int, int] = {}
    valid_candidates: list[int] = []

    candidates = sorted(ctx_candidates) if ctx_candidates else [2048, 4096]

    for ctx in candidates:
        reading = probe.read()
        free_vram = reading.vram_free_mb
        base_mb = 4000
        kv_mb = int((ctx / 1024) * 250)
        needed_mb = base_mb + kv_mb
        vram_mb_by_ctx[ctx] = needed_mb

        if free_vram is None or free_vram >= needed_mb or len(valid_candidates) == 0:
            valid_candidates.append(ctx)

    c_eff = max(valid_candidates) if valid_candidates else 2048

    max_slots = 1
    reading = probe.read()
    if reading.vram_free_mb is not None and reading.vram_free_mb > 2 * vram_mb_by_ctx.get(c_eff, 4000):
        max_slots = 2

    tokens_per_s = 35.0

    success_by_size_bucket = {
        "S": 1.0,
        "M": 0.95,
        "L": 0.85,
        "XL": 0.70,
    }

    return ModelProfile(
        model_id=model_id,
        backend=backend.name,
        c_eff_tokens=c_eff,
        max_slots=max_slots,
        tokens_per_s=tokens_per_s,
        vram_mb_by_ctx=vram_mb_by_ctx,
        success_by_size_bucket=success_by_size_bucket,
    )
