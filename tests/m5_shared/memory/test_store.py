# FILE: tests/m5_shared/memory/test_store.py
# ROLE: Tests for src/asf/m5_shared/memory/store.py.
# ARCH REF: M5; p12 Context & Memory Service; docs/architecture/MEMORY_ARCHITECTURE.md
# OWNS: Tests of store
# DOES NOT OWN: Production code
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/memory/store.py: MemoryRecord, MemoryStore, row_caps (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/memory/test_store.py` on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/memory/test_store.py` and `uv run mypy tests/m5_shared/memory/test_store.py` are clean.

import sqlite3

import pytest

from asf.m5_shared.memory.store import MemoryRecord, MemoryStore, row_caps


@pytest.fixture
def store() -> MemoryStore:
    conn = sqlite3.connect(":memory:")
    return MemoryStore(conn, caps={"episodic": 5, "semantic": 5, "procedural": 5, "session": 5})


def _lesson(run: str, text: str = "the gateway timed out; raise the timeout to 120 s") -> MemoryRecord:
    return MemoryRecord(layer="episodic", topic="failure/TIMEOUT", title="gateway timeout", text=text, tags=["lesson"], run_id=run)


def test_identical_records_are_stored_once_and_count_each_run_as_evidence(store: MemoryStore) -> None:
    a = store.remember(_lesson("r1"))
    b = store.remember(_lesson("r2"))
    assert a == b and store.stats()["episodic"] == 1
    assert store.search("gateway timeout", ["episodic"])[0].runs == ["r1", "r2"]


def test_search_returns_the_relevant_record_and_drops_weak_matches(store: MemoryStore) -> None:
    store.remember(MemoryRecord(layer="semantic", topic="src/db.py", title="sqlite busy timeout", text="the store sets busy_timeout to 5000 ms"))
    store.remember(MemoryRecord(layer="semantic", topic="src/web.py", title="web port", text="the viewer listens on 8765"))
    found = store.search("sqlite busy_timeout", ["semantic"])
    assert [r.topic for r in found] == ["src/db.py"]
    assert store.search("", ["semantic"]) == []


def test_search_works_without_fts5(store: MemoryStore) -> None:
    store.fts = False
    store.remember(MemoryRecord(layer="semantic", title="sqlite busy timeout", text="busy_timeout is 5000 ms"))
    assert store.search("sqlite timeout", ["semantic"])[0].title == "sqlite busy timeout"


def test_each_layer_keeps_to_its_row_share_by_dropping_the_least_useful(store: MemoryStore) -> None:
    keep = store.remember(MemoryRecord(layer="semantic", title="useful", text="fact 0"))
    store.mark_outcome([keep], helpful=True)
    for i in range(1, 8):
        store.remember(MemoryRecord(layer="semantic", title=f"fact {i}", text=f"fact number {i}"))
    assert store.stats()["semantic"] == 5
    assert store.search("useful", ["semantic"])[0].id == keep


def test_rows_are_derived_from_the_disk_share() -> None:
    caps = row_caps(10, {"avg_row_bytes": 1024, "episodic_pct": 45, "semantic_pct": 25, "procedural_pct": 10, "session_pct": 20})
    assert caps == {"episodic": 4608, "semantic": 2560, "procedural": 1024, "session": 2048}


def test_playbook_rules_that_mostly_hurt_are_retired(store: MemoryStore) -> None:
    rule = store.remember(MemoryRecord(layer="procedural", title="always use diff_edit", text="prefer diffs"))
    store.mark_outcome([rule], helpful=True)
    assert store.mark_outcome([rule], helpful=False) == []
    assert store.mark_outcome([rule], helpful=False) == [rule]
    assert store.stats()["procedural"] == 0


def test_facts_are_invalidated_when_their_source_changes(store: MemoryStore) -> None:
    store.remember(MemoryRecord(layer="semantic", topic="src/a.py", title="a", text="uses pathlib", source_hash="h1"))
    store.remember(MemoryRecord(layer="semantic", topic="src/b.py", title="b", text="uses httpx", source_hash="h2"))
    assert store.invalidate({"src/a.py": "h1", "src/b.py": "CHANGED"}) == 1
    assert [r.topic for r in store.iter_records(["semantic"])] == ["src/a.py"]


def test_a_finished_session_becomes_one_episode(store: MemoryStore) -> None:
    for note in ("planned 3 modules", "task greet verified"):
        store.remember(MemoryRecord(layer="session", scope="run:r1", title=note, text=note, run_id="r1"))
    episode = store.end_session("r1", "DONE")
    assert episode is not None and store.stats() == {"episodic": 1, "semantic": 0, "procedural": 0, "session": 0}
    assert store.end_session("r1", "DONE") is None


def test_a_lesson_seen_in_two_runs_is_promoted_to_the_playbook(store: MemoryStore) -> None:
    store.remember(_lesson("r1"))
    assert store.promote() == []
    store.remember(_lesson("r2"))
    assert len(store.promote()) == 1 and store.stats()["procedural"] == 1
    untrusted = MemoryRecord(layer="episodic", title="from mcp", text="do X", tags=["lesson"], trusted=False, run_id="r1")
    store.remember(untrusted)
    store.remember(untrusted.model_copy(update={"run_id": "r2"}))
    assert len(store.promote()) == 1  # untrusted lessons are never promoted
