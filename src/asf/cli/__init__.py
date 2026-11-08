# FILE: src/asf/cli/__init__.py
# ROLE: Marks cli as a package. M1 User Interface & Input: the `factory` CLI (drawio page 02).
# ARCH REF: M1; p02; D-11; D-12
# OWNS: Package marker only
# DOES NOT OWN: Any logic
# CONNECTS TO (external boundaries only):
#   - imports from none: none
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) `uv run python scripts/check_headers.py` reports no problem for this file. (2) `uv run ruff check src/asf/cli/__init__.py` and `uv run mypy src/asf/cli/__init__.py` are clean.

"""M1 User Interface & Input: the `factory` CLI (drawio page 02)."""
