# FILE: tests/cli/test_context.py
# ROLE: Tests that prove src/asf/cli/context.py meets its DONE WHEN conditions.
# ARCH REF: M1; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/context.py
# DOES NOT OWN: Production code
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/context.py: EXIT_OK, EXIT_USER, EXIT_ENV, project_root, state_db, open_store, renderer_for, latest_run_id, resolve_run_id (unit under test)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (a real project database)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/test_context.py` on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/test_context.py` and `uv run mypy tests/cli/test_context.py` are clean.

from pathlib import Path

import pytest

from asf.cli.context import EXIT_ENV, EXIT_OK, EXIT_USER, latest_run_id, open_store, project_root, renderer_for, resolve_run_id, state_db
from asf.m5_shared.state_store.store import StateStore


def _project(tmp_path: Path) -> StateStore:
    return StateStore.open(tmp_path / ".factory" / "state.db")


def _run(store: StateStore, run_id: str, activity: str) -> None:
    with store.conn:
        store.conn.execute(
            "INSERT INTO runs (run_id, project_id, status, version, created_at, last_activity, cost, cost_estimated, payload) "
            "VALUES (?, 'p', 'DONE', 1, 't', ?, 0, 0, '{}')",
            (run_id, activity),
        )


def test_exit_codes() -> None:
    assert (EXIT_OK, EXIT_USER, EXIT_ENV) == (0, 1, 2)


def test_the_project_is_the_current_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert project_root() == tmp_path.resolve()
    assert state_db() == tmp_path.resolve() / ".factory" / "state.db"


def test_a_missing_project_is_a_config_error_that_names_the_fix(tmp_path: Path) -> None:
    with pytest.raises(Exception) as info:  # noqa: PT011 - ConfigError lives in contracts, which this test does not import
        open_store(root=tmp_path)
    assert type(info.value).__name__ == "NoProjectError" and "factory init" in str(info.value)


def test_the_store_can_be_opened_read_only_and_cannot_write(tmp_path: Path) -> None:
    _project(tmp_path).close()
    reader = open_store(readonly=True, root=tmp_path)
    assert reader.readonly is True
    with pytest.raises(Exception):  # noqa: B017, PT011 - sqlite raises its own error type for a read-only connection
        reader.conn.execute("INSERT INTO meta VALUES ('x', 'y')")


def test_the_latest_run_is_the_most_recently_active(tmp_path: Path) -> None:
    store = _project(tmp_path)
    assert latest_run_id(store) is None
    _run(store, "old", "2026-01-01")
    _run(store, "new", "2026-06-01")
    assert latest_run_id(store) == "new"
    assert resolve_run_id(store, None) == "new" and resolve_run_id(store, "old") == "old"


def test_no_runs_is_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(Exception) as info:  # noqa: PT011
        resolve_run_id(_project(tmp_path), None)
    assert "factory run start" in str(info.value)


def test_renderer_for_validates_the_mode() -> None:
    assert renderer_for("json").mode.value == "json"
    with pytest.raises(Exception) as info:  # noqa: PT011
        renderer_for("fancy")
    assert type(info.value).__name__ == "ConfigError"
