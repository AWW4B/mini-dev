# FILE: tests/cli/ui/test_menus.py
# ROLE: Tests that prove src/asf/cli/ui/menus.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02; D-11b; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/ui/menus.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/ui/menus.py: is_interactive, choose, ask_text, confirm (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/ui/test_menus.py` on Windows and Linux once src/asf/cli/ui/menus.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/ui/test_menus.py` and `uv run mypy tests/cli/ui/test_menus.py` are clean.

import sys
from typing import Any

import pytest
import questionary

from asf.cli.ui.menus import ask_text, choose, confirm, is_interactive


class _Question:
    def __init__(self, answer: Any) -> None:
        self.answer = answer

    def ask(self) -> Any:
        return self.answer


def _tty(monkeypatch: pytest.MonkeyPatch, value: bool) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: value, raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: value, raising=False)


def test_interactive_needs_both_stdin_and_stdout_to_be_terminals(monkeypatch: pytest.MonkeyPatch) -> None:
    _tty(monkeypatch, True)
    assert is_interactive() is True
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
    assert is_interactive() is False


@pytest.mark.parametrize("call", [lambda: choose("t", ["a"]), lambda: ask_text("p"), lambda: confirm("c")])
def test_prompts_refuse_to_run_without_a_terminal(monkeypatch: pytest.MonkeyPatch, call: Any) -> None:
    _tty(monkeypatch, False)
    with pytest.raises(Exception) as info:  # noqa: PT011 - ConfigError lives in contracts, which this test does not import
        call()
    assert type(info.value).__name__ == "ConfigError" and "interactive terminal" in str(info.value)


def test_choose_returns_the_selected_option_and_only_passes_a_valid_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _tty(monkeypatch, True)
    seen: dict[str, Any] = {}

    def fake_select(title: str, choices: list[str], default: Any = None) -> _Question:
        seen.update(title=title, choices=choices, default=default)
        return _Question("beta")

    monkeypatch.setattr(questionary, "select", fake_select)
    assert choose("Pick", ["alpha", "beta"], default="beta") == "beta" and seen["default"] == "beta"
    choose("Pick", ["alpha", "beta"], default="gamma")
    assert seen["default"] is None


def test_ask_text_and_confirm(monkeypatch: pytest.MonkeyPatch) -> None:
    _tty(monkeypatch, True)
    calls: list[Any] = []

    def fake_text(prompt: str, default: str = "", multiline: bool = False) -> _Question:
        calls.append((prompt, default, multiline))
        return _Question("hi")

    monkeypatch.setattr(questionary, "text", fake_text)
    monkeypatch.setattr(questionary, "confirm", lambda prompt, default=False: _Question(True))
    assert ask_text("Name?", default="x", multiline=True) == "hi" and calls == [("Name?", "x", True)]
    assert confirm("Sure?") is True


def test_ctrl_c_at_a_prompt_becomes_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    _tty(monkeypatch, True)
    monkeypatch.setattr(questionary, "select", lambda *a, **k: _Question(None))
    monkeypatch.setattr(questionary, "confirm", lambda *a, **k: _Question(None))
    with pytest.raises(KeyboardInterrupt):
        choose("t", ["a"])
    with pytest.raises(KeyboardInterrupt):
        confirm("c")
