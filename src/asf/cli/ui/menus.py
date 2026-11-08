# FILE: src/asf/cli/ui/menus.py
# ROLE: Arrow-key menus and prompts (questionary, prompt_toolkit based) behind one small interface.
# ARCH REF: M1; p02; D-11b
# OWNS: Interactive selection and text prompts
# DOES NOT OWN: What the menu items do (flows.py)
# CONNECTS TO (external boundaries only):
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

def is_interactive() -> bool:
    raise NotImplementedError


def choose(title: str, options: list[str], default: str | None = None) -> str:
    raise NotImplementedError


def ask_text(prompt: str, default: str | None = None, multiline: bool = False) -> str:
    raise NotImplementedError


def confirm(prompt: str, default: bool = False) -> bool:
    raise NotImplementedError
