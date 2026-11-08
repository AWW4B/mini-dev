# FILE: tests/contracts/test_ids.py
# ROLE: Tests that prove src/asf/contracts/ids.py meets its DONE WHEN conditions.
# ARCH REF: p15; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/ids.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/ids.py: new_id, ProjectId, RunId, TaskId, AttemptId, EventId, DecisionId, LeaseId, CommandId, ContractId (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_ids.py` on Windows and Linux once src/asf/contracts/ids.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_ids.py` and `uv run mypy tests/contracts/test_ids.py` are clean.


from asf.contracts.ids import AttemptId, CommandId, ContractId, DecisionId, EventId, LeaseId, ProjectId, RunId, TaskId, new_id  # noqa: F401


def test_new_id_meets_contract() -> None:
    """Prove new_id behaves as declared in src/asf/contracts/ids.py."""
    raise NotImplementedError("write this test before implementing new_id")

def test_project_id_meets_contract() -> None:
    """Prove ProjectId behaves as declared in src/asf/contracts/ids.py."""
    raise NotImplementedError("write this test before implementing ProjectId")

def test_run_id_meets_contract() -> None:
    """Prove RunId behaves as declared in src/asf/contracts/ids.py."""
    raise NotImplementedError("write this test before implementing RunId")

def test_task_id_meets_contract() -> None:
    """Prove TaskId behaves as declared in src/asf/contracts/ids.py."""
    raise NotImplementedError("write this test before implementing TaskId")

def test_attempt_id_meets_contract() -> None:
    """Prove AttemptId behaves as declared in src/asf/contracts/ids.py."""
    raise NotImplementedError("write this test before implementing AttemptId")

def test_event_id_meets_contract() -> None:
    """Prove EventId behaves as declared in src/asf/contracts/ids.py."""
    raise NotImplementedError("write this test before implementing EventId")

def test_decision_id_meets_contract() -> None:
    """Prove DecisionId behaves as declared in src/asf/contracts/ids.py."""
    raise NotImplementedError("write this test before implementing DecisionId")

def test_lease_id_meets_contract() -> None:
    """Prove LeaseId behaves as declared in src/asf/contracts/ids.py."""
    raise NotImplementedError("write this test before implementing LeaseId")

def test_command_id_meets_contract() -> None:
    """Prove CommandId behaves as declared in src/asf/contracts/ids.py."""
    raise NotImplementedError("write this test before implementing CommandId")

def test_contract_id_meets_contract() -> None:
    """Prove ContractId behaves as declared in src/asf/contracts/ids.py."""
    raise NotImplementedError("write this test before implementing ContractId")
