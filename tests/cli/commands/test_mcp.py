# FILE: tests/cli/commands/test_mcp.py
# ROLE: Tests that prove src/asf/cli/commands/mcp.py meets its DONE WHEN conditions.
# ARCH REF: M1; p12; D-18; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/commands/mcp.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/mcp.py: mcp_list, mcp_test, register (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_mcp.py` on Windows and Linux once src/asf/cli/commands/mcp.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_mcp.py` and `uv run mypy tests/cli/commands/test_mcp.py` are clean.

import json
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from asf.cli.commands.mcp import mcp_list, mcp_test, register


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    monkeypatch.setenv("FACTORY_HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)


def test_no_servers_are_connected_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    assert mcp_list("json") == 0
    assert json.loads(capsys.readouterr().out)["rows"] == []


def test_testing_an_undeclared_server_is_refused_without_connecting(capsys: pytest.CaptureFixture[str]) -> None:
    assert mcp_test("evil") == 1
    assert "not declared in mcp.toml" in capsys.readouterr().err


def test_a_declared_server_is_listed_and_a_failing_test_is_reported(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import asf.cli.commands.mcp as mcp_mod

    class _Manager:
        def __init__(self, root: Any) -> None:
            pass

        def list_servers(self) -> list[str]:
            return ["files"]

        def test_server(self, name: str) -> Any:
            return type("R", (), {"reachable": False, "protocol_version": None, "tools": [], "problem": "connection refused"})()

    monkeypatch.setattr(mcp_mod, "McpManager", _Manager)
    assert mcp_list("json") == 0 and json.loads(capsys.readouterr().out)["rows"] == [{"name": "files"}]
    assert mcp_test("files") == 1
    assert "connection refused" in capsys.readouterr().out


def test_the_mcp_group_is_registered() -> None:
    app = typer.Typer()
    register(app)
    assert CliRunner().invoke(app, ["mcp", "list", "--output", "plain"]).exit_code == 0
