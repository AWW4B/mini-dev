# FILE: src/asf/m3_orchestration/decomposition/split_validator.py
# ROLE: Validates a split: coverage of parent acceptance, acyclic deps, progress rule (children smaller), file ownership disjointness.
# ARCH REF: M3; p05 split validation
# OWNS: Validation rules
# DOES NOT OWN: Generating proposals
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/decomposition/splitter.py: SplitProposal (input)
#   - imports from src/asf/contracts/tasks.py: TaskNode (parent)
#   - called by src/asf/m3_orchestration/decomposition/decomposition_graph.py: validate_split
#   - called by tests/m3_orchestration/decomposition/test_split_validator.py: validate_split
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/decomposition/test_split_validator.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/decomposition/split_validator.py` and `uv run mypy src/asf/m3_orchestration/decomposition/split_validator.py` are clean.

from asf.contracts.tasks import TaskNode
from asf.m3_orchestration.decomposition.splitter import SplitProposal


def validate_split(parent: TaskNode, proposal: SplitProposal) -> list[str]:
    """Return problems; empty means valid."""
    raise NotImplementedError
