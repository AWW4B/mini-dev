# FILE: tests/cli/commands/test_web.py
# ROLE: Tests that prove src/asf/cli/commands/web.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02 Active Group Chat; D-14b; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/commands/web.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/web.py: web, register (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_web.py` on Windows and Linux once src/asf/cli/commands/web.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_web.py` and `uv run mypy tests/cli/commands/test_web.py` are clean.

import importlib.util
import threading
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

import asf.cli.commands.web as web_mod
from asf.cli.commands.web import register, web


def test_a_missing_extra_exits_2_with_the_install_hint(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    assert web(None) == 2
    assert "uv sync --extra web" in capsys.readouterr().err


def test_the_viewer_is_served_on_loopback_only(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    served: list[tuple[Any, str, int]] = []
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(web_mod, "serve", lambda run_id, host, port: served.append((run_id, host, port)))
    assert web("run1", 9000, open_browser=False) == 0
    assert served == [("run1", "127.0.0.1", 9000)]
    assert "http://127.0.0.1:9000/" in capsys.readouterr().out


def test_the_default_port_and_browser_opening(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []
    served: list[int] = []
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(web_mod, "serve", lambda run_id, host, port: served.append(port))

    class _Timer:
        def __init__(self, delay: float, fn: Any, args: list[str]) -> None:
            opened.extend(args)

        def start(self) -> None:
            pass

    monkeypatch.setattr(threading, "Timer", _Timer)
    web(None)
    assert served == [8765] and opened == ["http://127.0.0.1:8765/"]


def test_ctrl_c_stops_only_the_viewer(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def boom(run_id: Any, host: str, port: int) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(web_mod, "serve", boom)
    assert web(None, open_browser=False) == 0
    assert "viewer stopped" in capsys.readouterr().out


def test_the_web_command_is_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    app = typer.Typer()
    register(app)
    assert CliRunner().invoke(app, ["--no-open"]).exit_code == 2
