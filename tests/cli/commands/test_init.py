# FILE: tests/cli/commands/test_init.py
# ROLE: Tests that prove src/asf/cli/commands/init.py meets its DONE WHEN conditions.
# ARCH REF: D-37; D-12; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/commands/init.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/init.py: init, register (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_init.py` on Windows and Linux once src/asf/cli/commands/init.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_init.py` and `uv run mypy tests/cli/commands/test_init.py` are clean.

import json
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from asf.cli.commands.init import init, register


def test_init_creates_user_config_the_project_state_and_registers_the_project(fake_paths: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "myproj"
    root.mkdir()
    assert init(root, False, "json") == 0
    assert (fake_paths.config_dir / "factory.toml").is_file() and (fake_paths.config_dir / "models.toml").is_file()
    assert (root / ".factory" / "state.db").is_file() and (root / ".factory" / ".gitignore").read_text(encoding="utf-8") == "*\n"
    registry = json.loads((fake_paths.data_dir / "projects.json").read_text(encoding="utf-8"))
    assert registry == {"myproj": str(root.resolve())}
    doc = json.loads(capsys.readouterr().out)
    assert doc["data"]["project"] == "myproj" and "state.db" in doc["data"]["created"]


def test_init_twice_changes_nothing_and_says_so(fake_paths: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "p"
    root.mkdir()
    init(root, False, "json")
    capsys.readouterr()
    (fake_paths.config_dir / "factory.toml").write_text("# my edits\nprofile = 'local'\n", encoding="utf-8")
    assert init(root, False, "json") == 0
    assert "already initialised" in json.loads(capsys.readouterr().out)["data"]["created"]
    assert "my edits" in (fake_paths.config_dir / "factory.toml").read_text(encoding="utf-8")


def test_force_rewrites_the_user_config_from_the_defaults(fake_paths: Any, tmp_path: Path) -> None:
    root = tmp_path / "p"
    root.mkdir()
    init(root, False, "plain")
    (fake_paths.config_dir / "factory.toml").write_text("profile = 'broken-edit'\n", encoding="utf-8")
    init(root, True, "plain")
    assert "broken-edit" not in (fake_paths.config_dir / "factory.toml").read_text(encoding="utf-8")


def test_the_init_command_is_registered_and_runs(fake_paths: Any, tmp_path: Path) -> None:
    app = typer.Typer()
    register(app)
    root = tmp_path / "viacli"
    root.mkdir()
    result = CliRunner().invoke(app, ["--path", str(root), "--output", "plain"])
    assert result.exit_code == 0 and (root / ".factory" / "state.db").is_file()
    assert "init" in [c.name for c in app.registered_commands]
