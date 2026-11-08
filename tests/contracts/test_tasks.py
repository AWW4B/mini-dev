# FILE: tests/contracts/test_tasks.py
# ROLE: Tests that prove src/asf/contracts/tasks.py meets its DONE WHEN conditions.
# ARCH REF: p05; p06 states; p15 TaskNode, LeafTaskSpec, AttemptRecord; IF-09 ReadyTask; A-2, A-3; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/tasks.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tasks.py: NodeKind, TaskState, NodeCounters, TaskNode, StepBudget, LeafTaskSpec, AttemptRecord (unit under test)
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use the tmp_path fixture or the fake_paths fixture for every filesystem location.
#   6. Use the fakes from tests/conftest.py instead of real GPUs, networks, sandboxes or model providers unless the test is marked needs_gpu, needs_network or needs_sandbox.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; real API keys; network access in unmarked tests; sleeping for timing (use the fake clock)
# ERRORS: Failures surface as pytest assertion failures.
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_tasks.py` on Windows and Linux once src/asf/contracts/tasks.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_tasks.py` and `uv run mypy tests/contracts/test_tasks.py` are clean.


from asf.contracts.tasks import AttemptRecord, LeafTaskSpec, NodeCounters, NodeKind, StepBudget, TaskNode, TaskState  # noqa: F401


def test_node_kind_meets_contract() -> None:
    """Prove NodeKind behaves as declared in src/asf/contracts/tasks.py."""
    raise NotImplementedError("write this test before implementing NodeKind")

def test_task_state_meets_contract() -> None:
    """Prove TaskState behaves as declared in src/asf/contracts/tasks.py."""
    raise NotImplementedError("write this test before implementing TaskState")

def test_node_counters_meets_contract() -> None:
    """Prove NodeCounters behaves as declared in src/asf/contracts/tasks.py."""
    raise NotImplementedError("write this test before implementing NodeCounters")

def test_task_node_meets_contract() -> None:
    """Prove TaskNode behaves as declared in src/asf/contracts/tasks.py."""
    raise NotImplementedError("write this test before implementing TaskNode")

def test_step_budget_meets_contract() -> None:
    """Prove StepBudget behaves as declared in src/asf/contracts/tasks.py."""
    raise NotImplementedError("write this test before implementing StepBudget")

def test_leaf_task_spec_meets_contract() -> None:
    """Prove LeafTaskSpec behaves as declared in src/asf/contracts/tasks.py."""
    raise NotImplementedError("write this test before implementing LeafTaskSpec")

def test_attempt_record_meets_contract() -> None:
    """Prove AttemptRecord behaves as declared in src/asf/contracts/tasks.py."""
    raise NotImplementedError("write this test before implementing AttemptRecord")
