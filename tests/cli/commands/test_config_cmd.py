# FILE: tests/cli/commands/test_config_cmd.py
# ROLE: Tests that prove src/asf/cli/commands/config_cmd.py meets its DONE WHEN conditions.
# ARCH REF: M1; D-37; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/commands/config_cmd.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/config_cmd.py: config_show, config_validate, register (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_config_cmd.py` on Windows and Linux once src/asf/cli/commands/config_cmd.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_config_cmd.py` and `uv run mypy tests/cli/commands/test_config_cmd.py` are clean.

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from asf.cli.commands.config_cmd import config_show, config_validate, register


def test_show_prints_the_effective_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("FACTORY_HOME", str(tmp_path))
    assert config_show("json") == 0
    data = json.loads(capsys.readouterr().out)["data"]
    assert data["profile"] == "hybrid" and "web" in data


def test_environment_variables_override_the_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("FACTORY_HOME", str(tmp_path))
    monkeypatch.setenv("FACTORY_PROFILE", "local-only")
    config_show("json")
    assert json.loads(capsys.readouterr().out)["data"]["profile"] == "local-only"


def test_validate_accepts_the_defaults_and_rejects_a_broken_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("FACTORY_HOME", str(tmp_path))
    assert config_validate() == 0
    config = tmp_path / "config"
    config.mkdir(parents=True, exist_ok=True)
    (config / "factory.toml").write_text("not = = toml [", encoding="utf-8")
    capsys.readouterr()
    assert config_validate() == 1
    assert "invalid" in capsys.readouterr().err


def test_an_unknown_output_mode_is_a_user_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FACTORY_HOME", str(tmp_path))
    app = typer.Typer()
    register(app)
    result = CliRunner().invoke(app, ["config", "show", "--output", "fancy"])
    assert result.exit_code == 1
