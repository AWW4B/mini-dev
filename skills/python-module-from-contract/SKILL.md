---
name: python-module-from-contract
description: Implement one Python module so that its pinned contract capsules and acceptance tests pass.
version: 1.0.0
allowed-tools: [read_file, search_code]
---
<!--
FILE: skills/python-module-from-contract/SKILL.md
ROLE: Agent Skill "python-module-from-contract": Implement one Python module so that its pinned contract capsules and acceptance tests pass.
ARCH REF: M4; p07; A-1; D-17; IF-23
OWNS: The procedure text loaded on demand by load_skill
DOES NOT OWN: Tool permissions (policy.toml) and model routing (gateway)
CONNECTS TO (external boundaries only):
  - called by src/asf/m5_shared/tools/skills.py: indexed and loaded via SkillsRegistry.load_body("python-module-from-contract")
  - called by src/asf/m4_execution/worker/strategies.py: requests this skill for role T2
  - emits/consumes: none
INSTRUCTIONS (strict, imperative):
  1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
  2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
  3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
  4. Open text files with encoding="utf-8" explicitly.
  5. Keep the frontmatter first (Agent Skills format) and the body under 400 lines; skills validate warns above the configured size.
  6. Write the procedure as numbered steps with one worked example; no model names, no absolute paths.
FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
DONE WHEN: (1) `uv run python scripts/check_headers.py` reports no problem for this file.
-->


# python-module-from-contract

Implement one Python module so that its pinned contract and its acceptance tests pass, changing nothing else.

## Inputs
- TASK: what to deliver, the files you may change (ALLOWED FILES), files you may only read.
- DEPENDENCY CONTRACTS: signatures, error cases and an example for each interface you use. Trust them; do not look for the implementation.
- ACCEPTANCE TESTS: the tests you must make pass. You may read them; you must not change them.

## Steps
1. Read the acceptance tests first. They say exactly what "done" means.
2. Read the files you were given and the contract lines. Note every signature you must keep exactly as written.
3. Implement the smallest code that satisfies the tests and the contract. Keep the declared names, parameters, return types and error types. Do not add features nobody asked for.
4. Write only inside ALLOWED FILES. A write anywhere else is denied by the platform; do not try to work around it.
5. Use the standard library and the dependencies already in the project. Never add or upgrade a dependency.
6. Use `pathlib.Path` for paths and argument lists for processes; never build shell strings. Open text files with `encoding="utf-8"`.
7. Run the acceptance tests with `run_tests` and the linter with `run_linter` on the files you changed. Read the failures, fix the code, run again.
8. Stop when the tests pass and the linter is clean, and report what you changed in one short paragraph. If you are stuck on something outside your files (the contract is missing an operation you need, or the context is too small), report `blocked` with the reason and the word CONTRACT_GAP or CONTEXT_OVERFLOW instead of guessing.

## Output
One JSON object per step: a tool call `{"action": "tool", "tool": "<name>", "args": {...}}`, or the end `{"action": "done", "message": "..."}` / `{"action": "blocked", "message": "..."}`.

## Example
```
{"action": "tool", "tool": "read_file", "args": {"rel_path": "tests/billing/test_refund.py"}}
{"action": "tool", "tool": "write_file", "args": {"rel_path": "src/billing/refund.py", "content": "..."}}
{"action": "tool", "tool": "run_tests", "args": {"selectors": ["tests/billing/test_refund.py"]}}
{"action": "done", "message": "Implemented refund(); both tests pass and ruff is clean."}
```
