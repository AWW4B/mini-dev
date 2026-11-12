# FILE: src/asf/m4_execution/integration/repair.py
# ROLE: Creates bounded repair tasks when an integration run fails.
# ARCH REF: M4; p08 repair; p06 REPAIRING
# OWNS: Repair task creation
# DOES NOT OWN: Running repairs (scheduler/worker)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tasks.py: TaskNode (repair node)
#   - called by src/asf/m4_execution/integration/integrator.py: make_repair_task
#   - called by tests/m4_execution/integration/test_repair.py: make_repair_task
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m4_execution/integration/test_repair.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m4_execution/integration/repair.py` and `uv run mypy src/asf/m4_execution/integration/repair.py` are clean.

from asf.contracts.tasks import TaskNode

MAX_REPAIR_ROUNDS = 2


def make_repair_task(parent: TaskNode, failure_ref: str, round_no: int) -> TaskNode | None:
    """Return a REPAIR node, or None when repair rounds are exhausted.

    ``round_no`` is the number of repair rounds already spent on ``parent`` (0 for the first failure).
    The repair is a bounded patch: the parent's files and contracts, the failing tests as its only acceptance.
    """
    if round_no < 0:
        raise ValueError("round_no must be >= 0")
    if round_no >= MAX_REPAIR_ROUNDS:
        return None
    attempt = round_no + 1
    return TaskNode.model_validate(
        {
            "id": f"{parent.id}-repair-{attempt}",
            "run_id": parent.run_id,
            "parent_id": parent.id,
            "kind": "repair",
            "goal": f"Repair the failing integration of '{parent.goal}': patch only; the failing tests in {failure_ref} are the acceptance criteria",
            "acceptance_refs": [failure_ref],
            "contract_refs": list(parent.contract_refs),
            "deps": [],
            "allowed_files": list(parent.allowed_files),
            "priority": parent.priority + 1,  # repairs run before the work that is waiting on them
            "state": "PROPOSED",
            "depth": parent.depth + 1,
            "counters": {"repair_rounds": attempt},
            "idempotency_key": f"repair:{parent.id}:{attempt}",
        }
    )
