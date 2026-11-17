# FILE: tests/cli/commands/test_memory_cmd.py
# ROLE: Tests for src/asf/cli/commands/memory_cmd.py.
# ARCH REF: M1; M5; p12 Context & Memory Service; docs/architecture/MEMORY_ARCHITECTURE.md
# OWNS: Tests of the memory commands
# DOES NOT OWN: Production code
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/memory_cmd.py: memory_plan, memory_search, memory_stats (unit under test)
#   - imports from src/asf/m5_shared/memory/store.py: MemoryRecord, open_memory_store (seed records)
#   - imports from tests/conftest.py: cli_project (a project directory)
#   - imports from src/asf/cli/context.py: EXIT_USER (exit codes)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_memory_cmd.py` on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_memory_cmd.py` and `uv run mypy tests/cli/commands/test_memory_cmd.py` are clean.

from typing import Any

import pytest

from asf.cli.commands.memory_cmd import memory_plan, memory_search, memory_stats
from asf.cli.context import EXIT_USER
from asf.m5_shared.memory.store import MemoryRecord, open_memory_store


def test_plan_shows_shares_models_and_layer_budgets(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    _ = cli_project
    assert memory_plan("plain") == 0
    out = capsys.readouterr().out
    assert "mini-dev may use" in out and "Context budget per call" in out and "working" in out


def test_search_finds_records_flat_and_through_the_tree(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    store = open_memory_store(cli_project.root / ".factory" / "memory.db")
    store.remember(MemoryRecord(layer="semantic", topic="src/db/store.py", title="WAL mode", text="the store enables WAL"))
    assert memory_search("WAL store", [], False, "plain") == 0
    assert "WAL mode" in capsys.readouterr().out
    assert memory_search("WAL store", ["semantic"], True, "plain") == 0
    out = capsys.readouterr().out
    assert "root ->" in out and "WAL mode" in out
    assert memory_search("x", ["dreams"], False, "plain") == EXIT_USER


def test_stats_counts_each_layer(cli_project: Any, capsys: pytest.CaptureFixture[str]) -> None:
    _ = cli_project
    assert memory_stats("plain") == 0
    out = capsys.readouterr().out
    assert "episodic" in out and "beta tree retrieval: false" in out
