# FILE: tests/config/test_loader.py
# ROLE: Tests that prove src/asf/config/loader.py meets its DONE WHEN conditions.
# ARCH REF: D-37; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/config/loader.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/loader.py: load_layered, write_user_toml (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/config/test_loader.py` on Windows and Linux once src/asf/config/loader.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/config/test_loader.py` and `uv run mypy tests/config/test_loader.py` are clean.


from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from asf.config.loader import load_layered, write_user_toml  # noqa: F401
from asf.config.paths import AppPaths


def test_load_layered_meets_contract(fake_paths: AppPaths, tmp_path: Path) -> None:
    """load_layered returns a dict merging defaults + user + project + env layers."""
    # With no user/project overrides, we still get package defaults for 'factory'
    result = load_layered("factory")
    assert isinstance(result, dict)
    # Package default sets 'profile' = 'hybrid'
    assert result.get("profile") == "hybrid"
    assert result.get("max_parallel_workers") == 1


def test_load_layered_user_override(fake_paths: AppPaths) -> None:
    """User TOML overrides the package default."""
    user_toml = fake_paths.config_dir / "factory.toml"
    user_toml.write_text("[web]\nport = 9999\n", encoding="utf-8")

    result = load_layered("factory")
    assert result.get("web", {}).get("port") == 9999
    # Non-overridden key still comes from defaults
    assert result.get("profile") == "hybrid"


def test_load_layered_project_override(fake_paths: AppPaths, tmp_path: Path) -> None:
    """Project .factory TOML overrides user TOML."""
    proj_root = tmp_path / "myproj"
    proj_root.mkdir()
    proj_factory = proj_root / ".factory"
    proj_factory.mkdir()
    (proj_factory / "factory.toml").write_text("max_parallel_workers = 8\n", encoding="utf-8")

    result = load_layered("factory", project_root=proj_root)
    assert result.get("max_parallel_workers") == 8


def test_load_layered_env_override(fake_paths: AppPaths, monkeypatch: pytest.MonkeyPatch) -> None:
    """FACTORY_* env vars override file layers."""
    monkeypatch.setenv("FACTORY_PROFILE", "local")
    result = load_layered("factory")
    assert result.get("profile") == "local"


def test_load_layered_cli_override(fake_paths: AppPaths) -> None:
    """cli_overrides wins over all file layers."""
    result = load_layered("factory", cli_overrides={"output": "plain"})
    assert result.get("output") == "plain"


def test_load_layered_unknown_name(fake_paths: AppPaths) -> None:
    """Unknown config name returns an empty dict (no defaults file exists)."""
    result = load_layered("does_not_exist_xyz")
    assert result == {}


def test_write_user_toml_meets_contract(fake_paths: AppPaths) -> None:
    """write_user_toml writes a TOML file and returns its path."""
    data: dict[str, Any] = {"profile": "local", "max_parallel_workers": 4}
    dest = write_user_toml("factory", data)
    assert dest.is_file()
    assert dest.name == "factory.toml"

    # Read it back and verify
    result = load_layered("factory")
    assert result.get("profile") == "local"
    assert result.get("max_parallel_workers") == 4


def test_write_user_toml_idempotent(fake_paths: AppPaths) -> None:
    """Calling write_user_toml twice merges cleanly."""
    write_user_toml("factory", {"profile": "hybrid"})
    write_user_toml("factory", {"output": "plain"})

    result = load_layered("factory")
    assert result.get("output") == "plain"
