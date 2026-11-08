<!--
FILE: LICENSE.header.md
ROLE: Custom source-available licence (research and non-commercial evaluation only). NOT an OSI open-source licence.
ARCH REF: FR-5; D-42; D-43
OWNS: Licence terms
DOES NOT OWN: Third-party licences (NOTICE)
CONNECTS TO (external boundaries only):
  - imports from none: none
  - emits/consumes: none
INSTRUCTIONS (strict, imperative):
  1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
  2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
  3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
  4. Open text files with encoding="utf-8" explicitly.
  5. Replace [YOUR NAME] and [YOUR EMAIL] before publishing.
  6. Have the text reviewed by a lawyer before publishing; no governing-law clause is included on purpose (D-43).
  7. Licence text has no comment syntax, so this sibling file carries the header.
FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
DONE WHEN: (1) Placeholders are filled and a legal review is recorded (scripts/check_headers.py prints a reminder until then). (2) `uv run python scripts/check_headers.py` reports no problem for this file.
-->
