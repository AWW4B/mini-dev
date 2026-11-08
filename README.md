<!--
FILE: README.md
ROLE: Short project README: what this skeleton is, how to install and run, where the plan lives.
ARCH REF: All pages (overview); D-40; FR-1..FR-6
OWNS: Getting-started text
DOES NOT OWN: Per-file plans (headers) and architecture (docs/architecture)
CONNECTS TO (external boundaries only):
  - imports from none: none
  - emits/consumes: none
INSTRUCTIONS (strict, imperative):
  1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
  2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
  3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
  4. Open text files with encoding="utf-8" explicitly.
  5. Keep it short; never turn it into a central plan.
FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
DONE WHEN: (1) `uv run python scripts/check_headers.py` reports no problem for this file.
-->

# AI Software Factory (skeleton)

Local-first software factory: a CLI (`factory`) that turns a request into a recursively
decomposed task tree, runs local coding workers in a sandbox, and verifies bottom-up.
This repository is a **skeleton**: every source file is a typed stub that raises
`NotImplementedError`, and **every file carries its own plan in its header**.
There is no central plan file.

- Architecture: `docs/architecture/AI_Software_Factory_Architecture.drawio` (header in its `.header.md`).
- Rules for coding agents: `AGENTS.md`.
- Licence: source-available, research and non-commercial evaluation only. **Not open source.** See `LICENSE` and `NOTICE`.

## Requirements

Python 3.12-3.14, [uv](https://docs.astral.sh/uv/), git. Optional: ripgrep, bubblewrap (Linux) or srt (Windows/Linux)
for the tier-A sandbox, llama.cpp `llama-server` or Ollama for local models. Run `factory doctor` to check everything.

## Install and check

```
uv sync --locked                 # add --extra web for the read-only viewer
uv run factory doctor
uv run python scripts/check_headers.py --coverage
uv run python scripts/scan_forbidden.py
uv run pytest
```

## Working on a file

Open the file, read its header, implement only that file, and make its DONE WHEN checks pass.
