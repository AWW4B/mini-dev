# FILE: tests/m5_shared/context/test_memory.py
# ROLE: Tests that prove src/asf/m5_shared/context/memory.py meets its DONE WHEN conditions.
# ARCH REF: M5; p12 memory; D-32; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/context/memory.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/context/memory.py: ProjectMemory (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/context/test_memory.py` on Windows and Linux once src/asf/m5_shared/context/memory.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/context/test_memory.py` and `uv run mypy tests/m5_shared/context/test_memory.py` are clean.

import logging
import sqlite3
from types import SimpleNamespace

import pytest

from asf.m5_shared.context.memory import ProjectMemory


def test_project_memory_meets_contract() -> None:
    """Prove ProjectMemory behaves as declared in src/asf/m5_shared/context/memory.py."""
    mem = ProjectMemory()

    # 1. Record decisions
    mem.record_decision(
        text="Use SQLite in WAL mode for single writer state store.",
        tags=["database", "storage"],
        source_hashes={"src/storage.py": "hash_v1"},
    )
    mem.record_decision(
        text="Use Typer for the CLI interface.",
        tags=["cli", "ui"],
        source_hashes={"src/cli.py": "hash_cli_v1"},
    )

    # 2. Query relevant by tag
    db_decisions = mem.relevant(["database"])
    assert len(db_decisions) == 1
    assert "SQLite" in db_decisions[0]

    cli_decisions = mem.relevant(["cli"])
    assert len(cli_decisions) == 1
    assert "Typer" in cli_decisions[0]

    both = mem.relevant(["database", "ui"])
    assert len(both) == 2

    empty_tag = mem.relevant(["nonexistent"])
    assert len(empty_tag) == 0

    # 3. Invalidate on source file hash change
    # If storage.py changes hash, the database decision should be invalidated
    invalidated_count = mem.invalidate_changed({"src/storage.py": "hash_v2"})
    assert invalidated_count == 1

    # Database decision no longer returned
    assert len(mem.relevant(["database"])) == 0
    # CLI decision remains valid
    assert len(mem.relevant(["cli"])) == 1


class _BrokenConn:
    """A connection whose writes fail, standing in for a locked or full database."""

    def __enter__(self) -> "_BrokenConn":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def execute(self, sql: str, *_args: object) -> object:
        if sql.lstrip().upper().startswith("CREATE"):
            return None
        raise sqlite3.OperationalError("database is locked")


def test_a_failed_save_is_logged_and_the_decision_stays_usable_in_memory(caplog: pytest.LogCaptureFixture) -> None:
    store = SimpleNamespace(conn=_BrokenConn())
    memory = ProjectMemory(store)  # type: ignore[arg-type]
    with caplog.at_level(logging.ERROR):
        memory.record_decision("use sqlite", ["db"], {})
    assert memory.relevant(["db"]) == ["use sqlite"]
    assert any("could not persist decision" in r.getMessage() for r in caplog.records)
