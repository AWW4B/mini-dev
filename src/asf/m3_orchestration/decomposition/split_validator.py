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

ALPHA = 0.8  # every child must be at most alpha times the size of its parent (termination guarantee 1)
MIN_CHILDREN = 2
MAX_CHILDREN = 8


def _cycle(children: list[TaskNode]) -> list[str]:
    """Children that sit on a dependency cycle (Kahn's algorithm over sibling dependencies)."""
    ids = {str(c.id) for c in children}
    remaining = {str(c.id): {str(d) for d in c.deps if str(d) in ids} for c in children}
    while True:
        free = [n for n, deps in remaining.items() if not deps]
        if not free:
            return sorted(remaining)
        for n in free:
            del remaining[n]
        for deps in remaining.values():
            deps.difference_update(free)


def validate_split(parent: TaskNode, proposal: SplitProposal, *, alpha: float = ALPHA) -> list[str]:
    """Return problems; empty means valid.

    Checks: shape and ids, coverage of the parent's acceptance, an acyclic dependency graph, disjoint file ownership (and
    files inside the parent's), no duplicate children, and the progress rule S(child) <= alpha * S(parent) when sizes are set.
    """
    problems: list[str] = []
    children = proposal.children
    if proposal.parent_id != str(parent.id):
        problems.append(f"the proposal is for '{proposal.parent_id}', not for '{parent.id}'")
    if not MIN_CHILDREN <= len(children) <= MAX_CHILDREN:
        problems.append(f"a split needs {MIN_CHILDREN} to {MAX_CHILDREN} children, got {len(children)}")
    ids = [str(c.id) for c in children]
    problems += [f"child id '{i}' appears twice" for i in dict.fromkeys(i for i in ids if ids.count(i) > 1)]
    keys = [c.idempotency_key for c in children]
    if len(set(keys)) != len(keys):
        problems.append("two children are duplicates (same goal and contract slice)")

    # coverage: every acceptance criterion of the parent is claimed by some child
    claimed = {a for c in children for a in c.acceptance_refs}
    problems += [f"acceptance criterion '{a}' of the parent is not covered by any child" for a in parent.acceptance_refs if a not in claimed]

    # dependencies: siblings only, no cycles
    for c in children:
        for dep in c.deps:
            if str(dep) == str(c.id):
                problems.append(f"child '{c.id}' depends on itself")
    on_cycle = _cycle(children)
    if on_cycle:
        problems.append(f"the child dependencies contain a cycle among: {', '.join(on_cycle)}")

    # file ownership: disjoint between children, and inside the parent's own files
    owner: dict[str, str] = {}
    parent_files = set(parent.allowed_files)
    for c in children:
        if not c.allowed_files:
            problems.append(f"child '{c.id}' owns no files")
        for f in c.allowed_files:
            if f in owner and owner[f] != str(c.id):
                problems.append(f"file '{f}' is owned by both '{owner[f]}' and '{c.id}'")
            owner.setdefault(f, str(c.id))
            if parent_files and f not in parent_files:
                problems.append(f"child '{c.id}' owns '{f}', which is outside the parent's files")

    # progress: strictly smaller, so decomposition terminates
    if parent.size_estimate is not None:
        limit = alpha * parent.size_estimate
        for c in children:
            if c.size_estimate is not None and c.size_estimate > limit:
                problems.append(f"child '{c.id}' is not smaller enough: size {c.size_estimate} > {alpha} x {parent.size_estimate}")
    return list(dict.fromkeys(problems))
