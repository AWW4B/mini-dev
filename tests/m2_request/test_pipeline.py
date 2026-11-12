# FILE: tests/m2_request/test_pipeline.py
# ROLE: Tests that prove src/asf/m2_request/pipeline.py meets its DONE WHEN conditions.
# ARCH REF: M2; p03; D-04; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m2_request/pipeline.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m2_request/pipeline.py: build_request_graph (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m2_request/test_pipeline.py` on Windows and Linux once src/asf/m2_request/pipeline.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m2_request/test_pipeline.py` and `uv run mypy tests/m2_request/test_pipeline.py` are clean.

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from asf.m2_request.pipeline import build_request_graph


def test_build_request_graph_meets_contract(tmp_path: Path) -> None:
    """Prove build_request_graph behaves as declared in src/asf/m2_request/pipeline.py."""
    graph = build_request_graph()
    assert graph is not None

    # Create dummy attachment document
    doc_path = tmp_path / "spec.txt"
    doc_path.write_text("System requirements:\n- Must log in securely", encoding="utf-8")

    # Create dummy repo
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "pyproject.toml").write_text("[project]\nname = 'test-pkg'", encoding="utf-8")

    state_input: dict[str, Any] = {
        "request_id": "req-pipe-01",
        "project_id": "proj-alpha",
        "prompt": "Fix authentication token expiration bug",
        "attachment_refs": [str(doc_path)],
        "repo_ref": str(repo_dir),
    }

    result = graph.invoke(state_input)
    assert isinstance(result, dict)
    assert "structured_request" in result
    structured = result["structured_request"]
    assert structured.request_id == "req-pipe-01"
    assert structured.task_type.value == "debug"
    assert len(structured.requirements) >= 1
    assert len(result.get("document_refs", [])) >= 1
    assert result.get("repo_profile") is not None


def test_build_request_graph_with_checkpointer() -> None:
    saver = MemorySaver()
    graph = build_request_graph(checkpointer=saver)
    assert graph is not None


class _FakeStore:
    """Duck-typed StateStore: just the outbox table and the connection the pipeline writes to."""

    def __init__(self) -> None:
        self.readonly = False
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            "CREATE TABLE outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE, run_id TEXT, "
            "payload TEXT, published INTEGER, created_at TEXT)"
        )

    def events(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT payload FROM outbox ORDER BY id").fetchall()
        return [json.loads(r[0]) for r in rows]


class _FakeBroker:
    def __init__(self) -> None:
        self.requests: list[Any] = []

    def request(self, req: Any) -> None:
        self.requests.append(req)


def _basic_input(**extra: Any) -> dict[str, Any]:
    return {"request_id": "req-ev-1", "project_id": "p", "prompt": "Fix the login bug", "attachment_refs": [], **extra}


def test_narrative_events_are_valid_envelopes_with_a_causation_chain() -> None:
    store = _FakeStore()
    result = build_request_graph().invoke(_basic_input(state_store=store))
    assert "structured_request" in result

    events = {e["event_id"]: e for e in store.events()}
    kinds = {e["kind"] for e in events.values()}
    assert {"task_received", "step_started", "handoff_sent", "handoff_received"} <= kinds
    for event in events.values():
        assert event["run_id"] == "req-ev-1"
        assert event["actor"]["role"] == "intake"
        assert event["correlation_id"] == "req-ev-1"
        assert event["causation_id"] is None or event["causation_id"] in events
    received = events["evt-req-ev-1-handoff_received"]
    assert received["causation_id"] == "evt-req-ev-1-handoff_sent"
    assert events["evt-req-ev-1-task_received"]["causation_id"] is None


def test_running_the_graph_twice_does_not_duplicate_events() -> None:
    store = _FakeStore()
    graph = build_request_graph()
    graph.invoke(_basic_input(state_store=store))
    first = len(store.events())
    graph.invoke(_basic_input(state_store=store))
    assert len(store.events()) == first


def test_read_only_store_receives_no_events() -> None:
    store = _FakeStore()
    store.readonly = True
    build_request_graph().invoke(_basic_input(state_store=store))
    assert store.events() == []


def test_unreadable_attachment_without_a_broker_is_an_error_not_silently_ignored(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    empty = tmp_path / "empty.txt"
    empty.write_bytes(b"")
    with pytest.raises(Exception) as info:  # noqa: PT011 - the class lives in document_ingestion, which is not imported here
        build_request_graph().invoke(_basic_input(attachment_refs=[str(empty)]))
    assert type(info.value).__name__ == "DocumentNotIngestible"


def test_unreadable_attachment_is_put_to_the_broker_then_the_graph_interrupts_and_resumes(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    empty = tmp_path / "empty.txt"
    empty.write_bytes(b"")
    broker = _FakeBroker()
    graph = build_request_graph(checkpointer=MemorySaver())
    config: Any = {"configurable": {"thread_id": "t-doc", "decision_broker": broker}}

    paused = graph.invoke(_basic_input(attachment_refs=[str(empty)]), config)
    assert "__interrupt__" in paused
    assert broker.requests[0].kind.value == "clarify"
    assert "skip_document" in broker.requests[0].options

    resumed = graph.invoke(Command(resume="skip_document"), config)
    assert resumed["structured_request"].request_id == "req-ev-1"
    assert resumed["document_refs"] == []


def test_aborting_at_the_prompt_stops_the_request(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    empty = tmp_path / "empty.txt"
    empty.write_bytes(b"")
    graph = build_request_graph(checkpointer=MemorySaver())
    config: Any = {"configurable": {"thread_id": "t-abort", "decision_broker": _FakeBroker()}}
    graph.invoke(_basic_input(attachment_refs=[str(empty)]), config)
    with pytest.raises(Exception) as info:  # noqa: PT011
        graph.invoke(Command(resume="abort"), config)
    assert type(info.value).__name__ == "DocumentNotIngestible"


def test_unsupported_repository_asks_before_continuing(tmp_path: Path) -> None:
    broker = _FakeBroker()
    graph = build_request_graph(checkpointer=MemorySaver())
    config: Any = {"configurable": {"thread_id": "t-repo", "decision_broker": broker}}
    missing = str(tmp_path / "no-such-repo")

    paused = graph.invoke(_basic_input(repo_ref=missing), config)
    assert "__interrupt__" in paused
    assert broker.requests[0].options == ["abort", "proceed_anyway"]

    done = graph.invoke(Command(resume="proceed_anyway"), config)
    assert done["structured_request"].request_id == "req-ev-1"


def test_unsupported_repository_abort_raises(tmp_path: Path) -> None:
    graph = build_request_graph(checkpointer=MemorySaver())
    config: Any = {"configurable": {"thread_id": "t-repo-abort", "decision_broker": _FakeBroker()}}
    graph.invoke(_basic_input(repo_ref=str(tmp_path / "gone")), config)
    with pytest.raises(Exception) as info:  # noqa: PT011
        graph.invoke(Command(resume="abort"), config)
    assert type(info.value).__name__ == "PolicyDenied"
