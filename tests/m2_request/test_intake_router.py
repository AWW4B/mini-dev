# FILE: tests/m2_request/test_intake_router.py
# ROLE: Tests that prove src/asf/m2_request/intake_router.py meets its DONE WHEN conditions.
# ARCH REF: M2; p03 Intake Router; IF-01 SubmitRequest; IF-02; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m2_request/intake_router.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m2_request/intake_router.py: submit (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m2_request/test_intake_router.py` on Windows and Linux once src/asf/m2_request/intake_router.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m2_request/test_intake_router.py` and `uv run mypy tests/m2_request/test_intake_router.py` are clean.

import json
from pathlib import Path
from typing import Any

import pytest

from asf.m2_request.intake_router import submit

SubmitRequest = submit.__globals__["SubmitRequest"]
StructuredRequest = submit.__globals__["StructuredRequest"]
StateStore = submit.__globals__["StateStore"]


class _FakeGraph:
    def __init__(self, response: Any = None) -> None:
        self.call_count = 0
        self.last_state: dict[str, Any] | None = None
        self.response = response

    def invoke(self, state: dict[str, Any]) -> Any:
        self.call_count += 1
        self.last_state = state
        if self.response is not None:
            return self.response
        return StructuredRequest(
            request_id=state["request_id"],
            project_id=state["project_id"],
            task_type="feature",
            requirements=[
                {
                    "req_id": "REQ-001",
                    "text": state["prompt"],
                    "source_ref": "prompt",
                }
            ],
            constraints=[],
            nfrs=[],
            acceptance=[],
            assumptions=[],
            open_questions=[],
            repo_profile=None,
        )


def test_submit_meets_contract(tmp_path: Path) -> None:
    """Prove submit behaves as declared in src/asf/m2_request/intake_router.py."""
    fake_graph = _FakeGraph()
    req = SubmitRequest(
        project_id="test-proj-01",
        text="Add user authentication and OAuth login",
        attachment_refs=["sha256:doc123", "sha256:doc456"],
        repo_ref="local/my-repo",
    )

    db_path = tmp_path / "state.db"
    store = StateStore.open(db_path)

    # 1. First submission
    res = submit(req, state_store=store, graph=fake_graph)
    assert isinstance(res, StructuredRequest)
    assert res.project_id == "test-proj-01"
    assert res.request_id.startswith("req-")
    assert fake_graph.call_count == 1

    # Check provenance
    last_state = fake_graph.last_state
    assert last_state is not None
    assert last_state["prompt_provenance"] == "user"
    assert last_state["prompt_trusted"] is True
    assert last_state["attachment_provenance"] == "document"
    assert last_state["attachment_trusted"] is False
    assert last_state["repo_provenance"] == "repo"
    assert last_state["repo_trusted"] is False

    # Check StateStore persistence and STATE_CHANGED event in outbox
    cur = store.conn.execute("SELECT payload FROM request_records")
    row = cur.fetchone()
    assert row is not None
    stored_data = json.loads(row[0])
    assert stored_data["request_id"] == res.request_id

    cur = store.conn.execute("SELECT payload FROM outbox")
    outbox_row = cur.fetchone()
    assert outbox_row is not None
    event_data = json.loads(outbox_row[0])
    assert event_data["kind"] == "STATE_CHANGED"
    assert event_data["entity"] == "request"
    assert event_data["entity_id"] == res.request_id

    # 2. Idempotency: duplicate request returns the existing request id and record
    res2 = submit(req, state_store=store, graph=fake_graph)
    assert res2.request_id == res.request_id
    # Graph should NOT be called again
    assert fake_graph.call_count == 1


def test_submit_invalid_request() -> None:
    with pytest.raises(ValueError, match="request must be an instance of SubmitRequest"):
        submit("not-a-submit-request")  # type: ignore[arg-type]


def test_submit_dict_output(monkeypatch: pytest.MonkeyPatch) -> None:
    req = SubmitRequest(
        project_id="test-proj-dict",
        text="Fix memory leak in background worker",
        attachment_refs=[],
    )
    fake_graph = _FakeGraph(
        response={
            "structured_request": {
                "request_id": "req-custom-99",
                "project_id": "test-proj-dict",
                "task_type": "debug",
                "requirements": [
                    {
                        "req_id": "REQ-001",
                        "text": "Fix memory leak",
                        "source_ref": "prompt",
                    }
                ],
                "constraints": [],
                "nfrs": [],
                "acceptance": [],
                "assumptions": [],
                "open_questions": [],
                "repo_profile": None,
            }
        }
    )
    res = submit(req, graph=fake_graph)
    assert isinstance(res, StructuredRequest)
    assert res.request_id == "req-custom-99"
    assert res.task_type.value == "debug"
