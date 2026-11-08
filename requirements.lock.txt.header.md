<!--
FILE: requirements.lock.txt.header.md
ROLE: Hashed requirements export of uv.lock (no dev deps) for pip-based installs.
ARCH REF: D-01; D-02; D-03; D-44
OWNS: pip-compatible pinned list
DOES NOT OWN: Resolution (uv.lock)
CONNECTS TO (external boundaries only):
  - called by scripts/export_requirements.py: writes this file
  - emits/consumes: none
INSTRUCTIONS (strict, imperative):
  1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
  2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
  3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
  4. Open text files with encoding="utf-8" explicitly.
  5. Regenerate with scripts/export_requirements.py; never edit by hand.
FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
DONE WHEN: (1) Matches `uv export --frozen --no-dev` output. (2) `uv run python scripts/check_headers.py` reports no problem for this file.
-->
