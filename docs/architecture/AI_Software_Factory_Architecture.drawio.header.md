<!--
FILE: docs/architecture/AI_Software_Factory_Architecture.drawio.header.md
ROLE: The architecture source of truth (17 pages: HLD, LLD1-5, sequences, contracts IF-01..IF-24, failure matrix) referenced by every ARCH REF.
ARCH REF: p00-p16; M1; M2; M3; M4; M5
OWNS: Architecture diagrams
DOES NOT OWN: Implementation (the headers translate pages into files)
CONNECTS TO (external boundaries only):
  - called by scripts/check_headers.py: --coverage reads IDs from this file
  - emits/consumes: none
INSTRUCTIONS (strict, imperative):
  1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
  2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
  3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
  4. Open text files with encoding="utf-8" explicitly.
  5. Change the diagram first, then the affected headers; scripts/check_headers.py --coverage reads the IF and module IDs from this file.
  6. Open with draw.io desktop or diagrams.net; editing it with comments would break the format, so this sibling file carries the header.
FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
DONE WHEN: (1) `uv run python scripts/check_headers.py` reports no problem for this file.
-->
