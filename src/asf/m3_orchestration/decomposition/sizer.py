# FILE: src/asf/m3_orchestration/decomposition/sizer.py
# ROLE: Deterministic size estimate S(n) and fit test against the calibrated ModelProfile.
# ARCH REF: M3; p05 sizing; p06 leaf-sizing model
# OWNS: Size estimate and fit verdict
# DOES NOT OWN: Rubric scoring (rubric.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tasks.py: TaskNode (node)
#   - imports from src/asf/contracts/models.py: ModelProfile (C_eff)
#   - imports from src/asf/m5_shared/gateway/tokenizers.py: count_tokens (D-31)
#   - called by src/asf/m3_orchestration/decomposition/decomposition_graph.py: estimate_size, fits_leaf
#   - called by tests/m3_orchestration/decomposition/test_sizer.py: estimate_size, fits_leaf
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Fit = tokens <= 0.6 * C_eff, files <= F, interfaces <= I (values from ModelProfile and config).
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/decomposition/test_sizer.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/decomposition/sizer.py` and `uv run mypy src/asf/m3_orchestration/decomposition/sizer.py` are clean.

from asf.contracts.models import ModelProfile
from asf.contracts.tasks import TaskNode


def estimate_size(node: TaskNode, context_tokens: int) -> int:
    raise NotImplementedError


def fits_leaf(node: TaskNode, size: int, profile: ModelProfile) -> bool:
    raise NotImplementedError
