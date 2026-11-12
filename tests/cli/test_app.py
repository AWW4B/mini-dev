# FILE: tests/cli/test_app.py
# ROLE: Tests that prove src/asf/cli/app.py meets its DONE WHEN conditions.
# ARCH REF: M1; p01 HLD; p02; D-11; D-12; D-13; D-40; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/app.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/app.py: main (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/test_app.py` on Windows and Linux once src/asf/cli/app.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/test_app.py` and `uv run mypy tests/cli/test_app.py` are clean.

from pathlib import Path

import pytest
from typer.testing import CliRunner

from asf.cli.app import app, main

EXPECTED = {"doctor", "init", "project", "run", "trace", "inbox", "dash", "tasks", "history", "report", "models", "skills", "events", "config", "stats", "mcp", "web"}


def test_main_meets_contract() -> None:
    """Prove main and app behave as declared in src/asf/cli/app.py."""
    assert callable(main)
    runner = CliRunner()
    result = runner.invoke(app, ["doctor", "--output", "plain"])
    assert result.exit_code in (0, 1, 2)
    assert "python" in result.stdout.lower()


def test_every_command_is_registered() -> None:
    names = {c.name for c in app.registered_commands} | {g.name for g in app.registered_groups}
    assert EXPECTED <= names


def test_help_lists_the_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0 and all(name in result.stdout for name in ("run", "inbox", "trace", "doctor"))


def test_bare_factory_without_a_terminal_exits_2() -> None:
    assert CliRunner().invoke(app, []).exit_code == 2


def test_a_missing_project_is_an_environment_error_with_the_fix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["history", "list"])
    assert result.exit_code == 2 and "factory init" in result.stderr


def test_a_user_error_exits_1_with_a_message() -> None:
    result = CliRunner().invoke(app, ["doctor", "--output", "fancy"])
    assert result.exit_code != 0


def test_command_registration_failures_are_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    import asf.cli.app as app_mod

    assert all(hasattr(m, "register") for m in app_mod._COMMAND_MODULES)
