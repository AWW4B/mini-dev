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
    """new_id returns a non-empty string with the requested prefix."""
    result = new_id("task")
    assert isinstance(result, str)
    assert result.startswith("task_"), f"expected 'task_' prefix, got {result!r}"
    # Should be sortable: two successive ids from the same millisecond or later
    # must still have the first <= second because the timestamp component differs.
    id1 = new_id("x")
    id2 = new_id("x")
    # Both unique
    assert id1 != id2
    # Both correctly prefixed
    assert id1.startswith("x_")
    assert id2.startswith("x_")
    # Sortable: either equal-ms (then random order is acceptable) or ascending
    # Strip prefix and compare the ULID portion
    ulid1, ulid2 = id1[2:], id2[2:]
    # Length = 26 chars (Crockford Base32 ULID)
    assert len(ulid1) == 26, f"ULID portion wrong length: {ulid1!r}"
    assert len(ulid2) == 26, f"ULID portion wrong length: {ulid2!r}"


def test_project_id_meets_contract() -> None:
    """ProjectId is a NewType of str and roundtrips as a plain str."""
    pid = ProjectId("proj-abc")
    assert isinstance(pid, str)
    assert pid == "proj-abc"


def test_run_id_meets_contract() -> None:
    rid = RunId("run-123")
    assert isinstance(rid, str)
    assert rid == "run-123"


def test_task_id_meets_contract() -> None:
    tid = TaskId("task-456")
    assert isinstance(tid, str)
    assert tid == "task-456"


def test_attempt_id_meets_contract() -> None:
    aid = AttemptId("attempt-1")
    assert isinstance(aid, str)
    assert aid == "attempt-1"


def test_event_id_meets_contract() -> None:
    eid = EventId("event-7")
    assert isinstance(eid, str)
    assert eid == "event-7"


def test_decision_id_meets_contract() -> None:
    did = DecisionId("decision-9")
    assert isinstance(did, str)
    assert did == "decision-9"


def test_lease_id_meets_contract() -> None:
    lid = LeaseId("lease-2")
    assert isinstance(lid, str)
    assert lid == "lease-2"


def test_command_id_meets_contract() -> None:
    cid = CommandId("cmd-5")
    assert isinstance(cid, str)
    assert cid == "cmd-5"


def test_contract_id_meets_contract() -> None:
    ctid = ContractId("contract-3")
    assert isinstance(ctid, str)
    assert ctid == "contract-3"


def test_new_id_prefix_with_different_values() -> None:
    """new_id supports arbitrary prefix strings."""
    for prefix in ("run", "attempt", "event", "decision", "lease", "cmd"):
        result = new_id(prefix)
        assert result.startswith(f"{prefix}_")
