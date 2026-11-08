<!--
FILE: docs/architecture/AI_Software_Factory_Research_and_Decisions.md.header.md
ROLE: Header for the research notes and architectural decision records (ADRs) companion document.
ARCH REF: p00-p16; D-01..D-45
OWNS: Header metadata for AI_Software_Factory_Research_and_Decisions.md
DOES NOT OWN: Architecture diagrams (AI_Software_Factory_Architecture.drawio)
CONNECTS TO (external boundaries only):
  - imports from none: none
  - emits/consumes: none
INSTRUCTIONS (strict, imperative):
  1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
  2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
  3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
  4. Open text files with encoding="utf-8" explicitly.
  5. This is a sibling header file for AI_Software_Factory_Research_and_Decisions.md which cannot carry an inline header due to its format.
FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
ERRORS: Not applicable (documentation file).
DONE WHEN: (1) `uv run python scripts/check_headers.py` reports no problem for this file.
-->
