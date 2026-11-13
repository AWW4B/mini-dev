# FILE: src/asf/cli/ui/menus.py
# ROLE: Arrow-key menus and prompts (questionary, prompt_toolkit based) behind one small interface.
# ARCH REF: M1; p02; D-11b
# OWNS: Interactive selection and text prompts
# DOES NOT OWN: What the menu items do (flows.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/errors.py: ConfigError (no terminal)
#   - called by src/asf/cli/flows.py: choose, ask_text, confirm, is_interactive
#   - called by tests/cli/ui/test_menus.py: is_interactive, choose, ask_text, confirm
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Raise asf.contracts.errors.AsfError if called when not on a TTY; callers check is_interactive() first.
#   6. Works in Windows Terminal, conhost and Linux terminals.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/cli/ui/test_menus.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/ui/menus.py` and `uv run mypy src/asf/cli/ui/menus.py` are clean.

import sys

from asf.contracts.errors import ConfigError


def is_interactive() -> bool:
    """True only when both stdin and stdout are terminals; guided flows and prompts need that."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _require_tty() -> None:
    if not is_interactive():
        raise ConfigError("This prompt needs an interactive terminal. Pass the values as command-line options instead.")


def _answered(value: object) -> object:
    if value is None:  # questionary returns None when the user presses Ctrl+C
        raise KeyboardInterrupt
    return value


def choose(title: str, options: list[str], default: str | None = None) -> str:
    _require_tty()
    import questionary  # prompt_toolkit costs about 0.3 s to load; only an interactive prompt needs it

    answer = questionary.select(title, choices=options, default=default if default in options else None).ask()
    return str(_answered(answer))


def ask_text(prompt: str, default: str | None = None, multiline: bool = False) -> str:
    _require_tty()
    import questionary

    answer = questionary.text(prompt, default=default or "", multiline=multiline).ask()
    return str(_answered(answer))


def confirm(prompt: str, default: bool = False) -> bool:
    _require_tty()
    import questionary

    return bool(_answered(questionary.confirm(prompt, default=default).ask()))
