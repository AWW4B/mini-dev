# FILE: src/asf/m5_shared/metrics/advisories.py
# ROLE: Turns snapshots, budgets and probes into soft/hard ResourceAdvisories (IF-20).
# ARCH REF: M5; p10; IF-20 ResourceAdvisory; p06 budgets
# OWNS: Threshold rules
# DOES NOT OWN: Acting on advisories (scheduler, run_control)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/metrics.py: MetricsSnapshot, ResourceAdvisory (IF-19/IF-20)
#   - imports from src/asf/contracts/budget.py: RunBudget (limits)
#   - called by tests/m5_shared/metrics/test_advisories.py: evaluate_thresholds
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/metrics/test_advisories.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/metrics/advisories.py` and `uv run mypy src/asf/m5_shared/metrics/advisories.py` are clean.

from asf.contracts.budget import RunBudget
from asf.contracts.metrics import MetricsSnapshot, ResourceAdvisory


def evaluate_thresholds(snapshot: MetricsSnapshot, budget: RunBudget) -> list[ResourceAdvisory]:
    raise NotImplementedError
