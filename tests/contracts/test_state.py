# FILE: tests/contracts/test_state.py
# ROLE: Tests that prove src/asf/contracts/state.py meets its DONE WHEN conditions.
# ARCH REF: p09 Project State Store; IF-16; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/state.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/state.py: StateCommit (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_state.py` on Windows and Linux once src/asf/contracts/state.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_state.py` and `uv run mypy tests/contracts/test_state.py` are clean.


from typing import Any

import pytest
from pydantic import ValidationError

from asf.contracts.state import StateCommit


def _event() -> dict[str, Any]:
    return {
        "event_id": "e1", "run_id": "r1", "seq": 1, "ts": "2026-11-12T10:00:00+00:00",
        "actor": {"kind": "service", "role": "scheduler", "name": "Scheduler"}, "kind": "state_changed", "correlation_id": "c1",
    }


def test_create_commit_uses_none_as_expected_version() -> None:
    commit = StateCommit.model_validate({"entity": "task", "entity_id": "t1", "expected_version": None, "mutation": {"state": "READY"}})
    assert commit.expected_version is None
    assert commit.events == []


def test_expected_version_must_be_stated() -> None:
    with pytest.raises(ValidationError):
        StateCommit.model_validate({"entity": "task", "entity_id": "t1", "mutation": {}})


def test_commit_carries_events_and_round_trips() -> None:
    commit = StateCommit.model_validate(
        {"entity": "task", "entity_id": "t1", "expected_version": 3, "mutation": {"state": "RUNNING"}, "events": [_event()]}
    )
    assert commit.events[0].kind == "state_changed"
    assert StateCommit.model_validate_json(commit.model_dump_json()) == commit


def test_commit_rejects_an_invalid_event() -> None:
    bad = _event()
    del bad["seq"]
    with pytest.raises(ValidationError):
        StateCommit.model_validate({"entity": "task", "entity_id": "t1", "expected_version": None, "mutation": {}, "events": [bad]})
