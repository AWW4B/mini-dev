---
name: reproduce-bug-as-failing-test
description: Reproduce a reported bug as a minimal failing pytest test before any fix.
version: 1.0.0
allowed-tools: [read_file, search_code]
---
<!--
FILE: skills/reproduce-bug-as-failing-test/SKILL.md
ROLE: Agent Skill "reproduce-bug-as-failing-test": Reproduce a reported bug as a minimal failing pytest test before any fix.
ARCH REF: M3; p04 DIAGNOSIS mode; D-17; IF-23
OWNS: The procedure text loaded on demand by load_skill
DOES NOT OWN: Tool permissions (policy.toml) and model routing (gateway)
CONNECTS TO (external boundaries only):
  - called by src/asf/m5_shared/tools/skills.py: indexed and loaded via SkillsRegistry.load_body("reproduce-bug-as-failing-test")
  - called by src/asf/m3_orchestration/planning/modes.py: requests this skill for role T3
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


# reproduce-bug-as-failing-test

Before anyone fixes a bug, reproduce it as the smallest pytest test that fails for the reported reason. The test then becomes the proof that the fix works.

## Inputs
- BUG REPORT: what happened, what was expected, any error text or stack trace.
- REPOSITORY CONTEXT: the modules and tests that are probably involved.

## Steps
1. Restate the bug in one sentence of the form "when X, the code does Y but should do Z".
2. Find the public function or command that a user would call to trigger X. Reproduce through that entry point, not through internals.
3. Build the smallest input that triggers it. Remove everything that is not needed: if the bug still happens without a step, delete the step.
4. Write one test, named `test_regression_<short_description>`, that asserts the correct behaviour Z (not the buggy one).
5. Run it on the current code. It must fail, and the failure must be the reported one. A test that fails for another reason (an import error, a typo) is not a reproduction: fix the test.
6. If you cannot make it fail, say so and list what you tried; do not claim a reproduction you did not see.
7. Do not fix the bug in this step and do not change existing tests.
8. Note where the failure points (file and function): that is the first hypothesis for the fix.

## Output
The test file path and content, the exact failing assertion or error, and the suspected location in one line.

## Example
Report: "`parse_price('1,5')` returns 15 instead of 1.5".
```python
from shop.pricing import parse_price


def test_regression_comma_is_a_decimal_separator():
    assert parse_price("1,5") == 1.5
```
Failure seen: `assert 15 == 1.5`. Suspect: `shop/pricing.py::parse_price` strips the comma.
