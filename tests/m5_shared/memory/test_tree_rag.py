# FILE: tests/m5_shared/memory/test_tree_rag.py
# ROLE: Tests for src/asf/m5_shared/memory/tree_rag.py.
# ARCH REF: M5; p12 Context & Memory Service; docs/architecture/MEMORY_ARCHITECTURE.md
# OWNS: Tests of tree_rag
# DOES NOT OWN: Production code
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/memory/tree_rag.py: build_tree, TreeRetriever (unit under test)
#   - imports from src/asf/m5_shared/memory/store.py: MemoryRecord, MemoryStore (memory fixture)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/memory/test_tree_rag.py` on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/memory/test_tree_rag.py` and `uv run mypy tests/m5_shared/memory/test_tree_rag.py` are clean.

import json
import sqlite3
from types import SimpleNamespace
from typing import Any

import pytest

from asf.m5_shared.memory.store import MemoryRecord, MemoryStore
from asf.m5_shared.memory.tree_rag import TreeRetriever, build_tree


@pytest.fixture
def store() -> MemoryStore:
    s = MemoryStore(sqlite3.connect(":memory:"))
    facts = [
        ("src/asf/m5_shared/state_store/store.py", "WAL mode", "the state store enables WAL and busy_timeout"),
        ("src/asf/m5_shared/state_store/schema.py", "schema version", "schema version 2 adds metrics columns"),
        ("src/asf/web/server.py", "loopback only", "the web viewer binds to 127.0.0.1 and is GET only"),
        ("src/asf/cli/app.py", "typer app", "the CLI registers every command group lazily"),
    ]
    for topic, title, text in facts:
        s.remember(MemoryRecord(layer="semantic", topic=topic, title=title, text=text))
    s.remember(MemoryRecord(layer="episodic", topic="failure/TIMEOUT", title="sqlite busy", text="database is locked under parallel writes"))
    return s


def test_the_tree_mirrors_layers_and_topic_paths_with_summaries(store: MemoryStore) -> None:
    root = build_tree(list(store.iter_records(["semantic", "episodic"])), max_depth=3)
    assert [c.title for c in root.children] == ["episodic", "semantic"]  # fixed layer order, whatever the insertion order
    assert root.size == 5 and "sqlite" in root.children[0].summary and root.children[1].size == 4
    leaves: list[Any] = []
    stack = [root]
    while stack:
        node = stack.pop()
        leaves += [c for c in node.children if c.is_leaf]
        stack += [c for c in node.children if not c.is_leaf]
    assert len(leaves) == 5  # every record is reachable, unchanged: the tree only indexes the data


def test_the_lexical_navigator_opens_the_relevant_branch_and_explains_itself(store: MemoryStore) -> None:
    got = TreeRetriever(store, beam=1, max_depth=4).retrieve("sqlite WAL busy_timeout in the state store", ["semantic"], 500)
    assert [r.title for r in got.records][0] == "WAL mode"
    assert all("web" not in step.opened[0] for step in got.trace if step.opened)
    assert got.trace[0].navigator == "lexical" and got.tokens <= 500


def test_the_budget_is_respected(store: MemoryStore) -> None:
    assert TreeRetriever(store).retrieve("state store schema WAL", ["semantic"], 1).records == []


class _Gateway:
    def __init__(self, answer: Any) -> None:
        self.answer = answer
        self.calls = 0

    def model_for(self, role: Any, purpose: str, output_schema: Any = None) -> Any:
        assert role == "T1" and purpose == "memory_navigation"
        outer = self

        class _M:
            def invoke(self, prompt: str) -> Any:
                outer.calls += 1
                return SimpleNamespace(content=outer.answer(prompt) if callable(outer.answer) else outer.answer)

        return _M()


def test_the_model_navigator_picks_branches_by_id(store: MemoryStore) -> None:
    def pick_web(prompt: str) -> str:
        menu = json.loads(prompt.split("BRANCHES:\n", 1)[1])
        return json.dumps({"open": [m["id"] for m in menu if m["title"] in ("semantic", "src", "asf", "web", "server.py")]})

    gateway = _Gateway(pick_web)
    got = TreeRetriever(store, navigator="model", gateway=gateway).retrieve("where does the viewer listen", ["semantic"], 500)
    assert gateway.calls >= 1 and any(step.navigator == "model" for step in got.trace)
    assert "loopback only" in [r.title for r in got.records]


def test_an_unusable_model_answer_falls_back_to_the_lexical_navigator(store: MemoryStore) -> None:
    got = TreeRetriever(store, navigator="model", gateway=_Gateway("I think the second one")).retrieve("WAL busy_timeout", ["semantic"], 500)
    assert got.records and all(step.navigator == "lexical" for step in got.trace)
