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


def calibrate(backend: LocalRuntimeBackend, model_id: str, ctx_candidates: list[int]) -> ModelProfile:
    raise NotImplementedError
