# FILE: tests/m5_shared/memory/test_router.py
# ROLE: Tests for src/asf/m5_shared/memory/router.py.
# ARCH REF: M5; p12 Context & Memory Service; docs/architecture/MEMORY_ARCHITECTURE.md
# OWNS: Tests of router
# DOES NOT OWN: Production code
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/memory/router.py: MemoryRouter, ROLE_LAYERS (unit under test)
#   - imports from src/asf/m5_shared/memory/device_budget.py: load_memory_config (packaged config)
#   - imports from src/asf/m5_shared/memory/budgets.py: budgets_for (per-role budgets)
#   - imports from src/asf/m5_shared/memory/store.py: MemoryRecord, MemoryStore (memory fixture)
#   - imports from tests/conftest.py: fake_paths (isolated app directories)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/memory/test_router.py` on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/memory/test_router.py` and `uv run mypy tests/m5_shared/memory/test_router.py` are clean.

import sqlite3
from types import SimpleNamespace
from typing import Any

import pytest

from asf.m5_shared.memory.budgets import budgets_for
from asf.m5_shared.memory.device_budget import load_memory_config
from asf.m5_shared.memory.router import ROLE_LAYERS, MemoryRouter
from asf.m5_shared.memory.store import MemoryRecord, MemoryStore


@pytest.fixture
def config(fake_paths: Any) -> dict[str, Any]:
    _ = fake_paths
    return load_memory_config()


@pytest.fixture
def store() -> MemoryStore:
    s = MemoryStore(sqlite3.connect(":memory:"))
    s.remember(MemoryRecord(layer="semantic", topic="src/greet.py", title="greeting format", text="greetings end with an exclamation mark"))
    s.remember(MemoryRecord(layer="procedural", topic="failure/IMPORT", title="import errors", text="when a test cannot import the module, check the src package path"))
    s.remember(MemoryRecord(layer="episodic", topic="failure/ASSERT", title="greet attempt 1 failed", text="greet returned Hi instead of the greeting format"))
    s.remember(MemoryRecord(layer="semantic", title="greeting format advice", text="greeting format advice from a web page", trusted=False))
    s.remember(MemoryRecord(layer="session", scope="run:r1", title="plan", text="greet module planned for the greeting", run_id="r1"))
    return s


class _Skills:
    def __init__(self) -> None:
        self.bodies = {"python-module-from-contract": "# python-module-from-contract\n1. Read the contract.\n", "characterisation-tests": "x" * 40_000}

    def lookup(self, capability: str, role: str) -> list[Any]:
        return [
            SimpleNamespace(name="python-module-from-contract", description="write a python module that implements a contract", body_chars=60),
            SimpleNamespace(name="characterisation-tests", description="pin legacy behaviour with tests", body_chars=40_000),
        ]

    def load_body(self, name: str) -> str:
        return self.bodies[name]


def test_the_tiny_model_gets_no_memory(store: MemoryStore, config: dict[str, Any]) -> None:
    routed = MemoryRouter(store, config).assemble("T1", "greeting", budgets_for("T1", 8192, config), run_id="r1")
    assert ROLE_LAYERS["T1"] == () and routed.items == []


def test_the_coder_gets_relevant_trusted_memory_within_each_layer_budget(store: MemoryStore, config: dict[str, Any]) -> None:
    budgets = budgets_for("T2", 8192, config)
    routed = MemoryRouter(store, config).assemble("T2", "implement the greeting format in greet", budgets, run_id="r1")
    refs = [d.ref for d in routed.included]
    assert any(r.startswith("semantic:") for r in refs) and any(r.startswith("session:") for r in refs)
    assert any(d.reason.startswith("untrusted") for d in routed.excluded)
    for layer in ("semantic", "episodic", "session", "procedural"):
        assert routed.tokens(layer) <= budgets.get(layer)
    assert len(routed.record_ids) == len([r for r in refs if not r.startswith("skill")])


def test_session_memory_needs_the_run_and_duplicates_are_skipped(store: MemoryStore, config: dict[str, Any]) -> None:
    routed = MemoryRouter(store, config).assemble("T3", "greeting format", budgets_for("T3", 32768, config))
    assert not any(d.layer == "session" for d in routed.included)
    fact = next(r for r in store.search("greeting format", ["semantic"]) if r.trusted)
    again = MemoryRouter(store, config).assemble("T3", "greeting format", budgets_for("T3", 32768, config), already={fact.content_hash})
    assert any(d.reason == "already in the prompt" for d in again.excluded)


def test_skills_are_disclosed_progressively(store: MemoryStore, config: dict[str, Any]) -> None:
    routed = MemoryRouter(store, config, skills=_Skills()).assemble("T2", "write a python module for the contract", budgets_for("T2", 16384, config))
    refs = [d.ref for d in routed.included]
    assert "skills:index" in refs and "skill:python-module-from-contract" in refs
    assert "skill:characterisation-tests" not in refs  # not relevant, and far too big for the procedural share


def test_the_beta_tree_retriever_can_replace_flat_search(store: MemoryStore, config: dict[str, Any]) -> None:
    beta = {**config, "beta": {**config["beta"], "tree_rag": True}}
    router = MemoryRouter(store, beta)
    assert router.tree is not None
    routed = router.assemble("T2", "greeting format greet", budgets_for("T2", 8192, beta), run_id="r1")
    assert any(d.ref.startswith("semantic:") for d in routed.included)
