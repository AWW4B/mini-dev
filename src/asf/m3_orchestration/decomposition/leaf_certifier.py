# FILE: src/asf/m3_orchestration/decomposition/leaf_certifier.py
# ROLE: Certifies a leaf: pins capsules (A-1), attaches T3 acceptance tests (A-4), and builds the LeafTaskSpec (IF-09).
# ARCH REF: M3; p05 leaf certification; IF-09 ReadyTask; A-1; A-4
# OWNS: LeafTaskSpec construction
# DOES NOT OWN: Scheduling
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tasks.py: TaskNode, LeafTaskSpec (IF-09)
#   - imports from src/asf/m5_shared/registry/registry.py: ContractRegistry (IF-07/IF-08)
#   - imports from src/asf/m3_orchestration/planning/test_authoring.py: author_acceptance_tests (A-4)
#   - called by src/asf/m3_orchestration/decomposition/decomposition_graph.py: certify_leaf
#   - called by tests/m3_orchestration/decomposition/test_leaf_certifier.py: certify_leaf
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/decomposition/test_leaf_certifier.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/decomposition/leaf_certifier.py` and `uv run mypy src/asf/m3_orchestration/decomposition/leaf_certifier.py` are clean.

from asf.contracts.tasks import LeafTaskSpec, TaskNode


def certify_leaf(node: TaskNode, base_commit: str, parent_branch: str) -> LeafTaskSpec:
    raise NotImplementedError
