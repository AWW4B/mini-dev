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
#   - called by tests/m3_orchestration/decomposition/test_sizer.py: FIT_FRACTION, estimate_size, fits_leaf
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
from asf.m5_shared.gateway.tokenizers import count_tokens

FIT_FRACTION = 0.6  # est_in + est_out must fit in 60% of the calibrated effective context
MAX_FILES = 3  # F_max
MAX_INTERFACES = 4  # I_max
MAX_RISK = 0.7  # R_max for the rubric's ambiguity / coupling scores
TOKENS_PER_FUNCTION = 150  # k, the output tokens per function to write (learnt per model in calibration)
TOKENS_PER_CRITERION = 120  # test code per acceptance criterion


def estimate_size(node: TaskNode, context_tokens: int) -> int:
    """S(n) = est_in + est_out, deterministic.

    est_in is the context the worker would receive (spec, pinned signatures, files, snippets: ``context_tokens``, counted by
    the caller with the model's tokenizer) plus the node's own spec. est_out is k tokens per function to write plus test code.
    """
    spec_tokens, _ = count_tokens("", " ".join([node.goal, *node.acceptance_refs]))
    functions = max(1, 2 * len(node.contract_refs) + len(node.acceptance_refs))
    est_out = TOKENS_PER_FUNCTION * functions + TOKENS_PER_CRITERION * len(node.acceptance_refs)
    return max(0, context_tokens) + spec_tokens + est_out


def fits_leaf(
    node: TaskNode,
    size: int,
    profile: ModelProfile,
    *,
    max_files: int = MAX_FILES,
    max_interfaces: int = MAX_INTERFACES,
    risk: float | None = None,
    max_risk: float = MAX_RISK,
) -> bool:
    """LEAF if S(n) <= 0.6 * C_eff AND files <= F AND interfaces <= I AND (when scored) rubric risk <= R."""
    return (
        size <= FIT_FRACTION * profile.c_eff_tokens
        and len(node.allowed_files) <= max_files
        and len(node.contract_refs) <= max_interfaces
        and (risk is None or risk <= max_risk)
    )
