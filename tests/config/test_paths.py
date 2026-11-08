# FILE: tests/config/test_paths.py
# ROLE: Tests that prove src/asf/config/paths.py meets its DONE WHEN conditions.
# ARCH REF: FR-4 (no hardcoded paths); D-26; D-37; D-45; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/config/paths.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/paths.py: AppPaths, get_paths (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/config/test_paths.py` on Windows and Linux once src/asf/config/paths.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/config/test_paths.py` and `uv run mypy tests/config/test_paths.py` are clean.


import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from asf.config.paths import AppPaths, get_paths  # noqa: F401


def test_app_paths_meets_contract(tmp_path: Path) -> None:
    """AppPaths fields are plain Path objects; helper methods return correct subpaths."""
    paths = AppPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        log_dir=tmp_path / "logs",
        cache_dir=tmp_path / "cache",
    )
    assert paths.config_dir == tmp_path / "config"
    assert paths.data_dir == tmp_path / "data"
    assert paths.log_dir == tmp_path / "logs"
    assert paths.cache_dir == tmp_path / "cache"

    # project_dir returns <root>/.factory
    proj_root = tmp_path / "myproject"
    proj_root.mkdir()
    proj_dir = paths.project_dir(proj_root)
    assert proj_dir == proj_root / ".factory"
    assert proj_dir.is_dir()  # created lazily

    # state_db lives inside project_dir
    state_db = paths.state_db(proj_root)
    assert state_db == proj_root / ".factory" / "state.db"

    # checkpoints_db lives inside project_dir
    ckpt_db = paths.checkpoints_db(proj_root)
    assert ckpt_db == proj_root / ".factory" / "checkpoints.db"


def test_get_paths_meets_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """get_paths() honours FACTORY_HOME and creates directories lazily."""
    monkeypatch.setenv("FACTORY_HOME", str(tmp_path))
    paths = get_paths()

    assert paths.config_dir == tmp_path / "config"
    assert paths.data_dir == tmp_path / "data"
    assert paths.log_dir == tmp_path / "logs"
    assert paths.cache_dir == tmp_path / "cache"

    # Directories must be created by get_paths
    for d in (paths.config_dir, paths.data_dir, paths.log_dir, paths.cache_dir):
        assert d.is_dir(), f"Expected {d} to exist"


def test_get_paths_without_factory_home(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_paths() without FACTORY_HOME uses platformdirs and returns an AppPaths."""
    monkeypatch.delenv("FACTORY_HOME", raising=False)
    paths = get_paths()
    assert isinstance(paths, AppPaths)
    # Directories should still be Path objects
    assert isinstance(paths.config_dir, Path)
    assert isinstance(paths.data_dir, Path)
