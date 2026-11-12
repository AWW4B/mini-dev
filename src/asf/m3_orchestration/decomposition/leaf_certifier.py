# FILE: src/asf/m3_orchestration/decomposition/leaf_certifier.py
# ROLE: Certifies a leaf: pins capsules (A-1), attaches T3 acceptance tests (A-4), and builds the LeafTaskSpec (IF-09).
# ARCH REF: M3; p05 leaf certification; IF-09 ReadyTask; A-1; A-4
# OWNS: LeafTaskSpec construction
# DOES NOT OWN: Scheduling
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tasks.py: TaskNode, LeafTaskSpec (IF-09)
#   - imports from src/asf/m5_shared/registry/registry.py: ContractRegistry (IF-07/IF-08)
#   - imports from src/asf/m3_orchestration/planning/test_authoring.py: author_acceptance_tests (A-4)
#   - imports from src/asf/contracts/contract_spec.py: ContractCapsule, ContractQuery (pinned capsules)
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

from collections.abc import Callable

from asf.contracts.contract_spec import ContractCapsule, ContractQuery
from asf.contracts.tasks import LeafTaskSpec, TaskNode
from asf.m3_orchestration.planning.test_authoring import author_acceptance_tests  # noqa: F401
from asf.m5_shared.registry.registry import ContractRegistry

CONTEXT_BUDGET_TOKENS = 8000
Authoring = Callable[[TaskNode], list[str]]


def _is_test_ref(ref: str) -> bool:
    path = ref.split("::")[0]
    return path.endswith(".py") and ("test_" in path.rsplit("/", 1)[-1])


def _capsules(node: TaskNode, registry: ContractRegistry | None) -> list[ContractCapsule]:
    """Pin the contract slices the leaf depends on (A-1): the pinned version of each, never an implementation."""
    if registry is None or not node.contract_refs:
        return []
    modules: list[str] = []
    pinned: dict[str, str] = {}
    for ref in node.contract_refs:
        module, _, version = ref.partition("@")
        modules.append(module)
        if version:
            pinned[module] = version
    return registry.query(ContractQuery(module_ids=modules, pinned_versions=pinned))


def certify_leaf(
    node: TaskNode,
    base_commit: str,
    parent_branch: str,
    *,
    registry: ContractRegistry | None = None,
    authoring: Authoring | None = None,
    context_budget_tokens: int = CONTEXT_BUDGET_TOKENS,
    read_only_files: list[str] | None = None,
) -> LeafTaskSpec:
    """Pin capsules (A-1), attach acceptance tests written by the planner tier (A-4) and build the IF-09 LeafTaskSpec.

    Acceptance refs that already are test files are used as they are; otherwise ``authoring(node)`` must write them (it is
    the planner-tier T3 author, see planning/test_authoring.py). A leaf never goes out without tests.
    """
    if not node.allowed_files:
        raise ValueError(f"Task {node.id} owns no files, so it cannot be a leaf")
    tests = [r for r in node.acceptance_refs if _is_test_ref(r)]
    if not tests:
        if authoring is None:
            raise ValueError(f"Task {node.id} has no acceptance tests and no authoring function was given (A-4)")
        tests = authoring(node)
        if not tests:
            raise ValueError(f"Task {node.id}: acceptance test authoring produced no tests")
    return LeafTaskSpec.model_validate(
        {
            "task_id": str(node.id),
            "goal": node.goal,
            "acceptance_test_refs": tests,
            "capsules": _capsules(node, registry),
            "allowed_files": list(node.allowed_files),
            "read_only_files": list(read_only_files or []),
            "context_budget_tokens": context_budget_tokens,
            "model_role": "T2",
            "base_commit": base_commit,
            "parent_branch": parent_branch,
        }
    )
