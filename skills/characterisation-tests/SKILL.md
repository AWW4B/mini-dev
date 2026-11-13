---
name: characterisation-tests
description: Pin current behaviour of existing code with characterisation tests before a refactor.
version: 1.0.0
allowed-tools: [read_file, search_code]
---
<!--
FILE: skills/characterisation-tests/SKILL.md
ROLE: Agent Skill "characterisation-tests": Pin current behaviour of existing code with characterisation tests before a refactor.
ARCH REF: M3; p04 IMPACT/REFACTOR mode; D-17; IF-23
OWNS: The procedure text loaded on demand by load_skill
DOES NOT OWN: Tool permissions (policy.toml) and model routing (gateway)
CONNECTS TO (external boundaries only):
  - called by src/asf/m5_shared/tools/skills.py: indexed and loaded via SkillsRegistry.load_body("characterisation-tests")
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


# characterisation-tests

Pin what existing code does today, before a refactor, so that any change in behaviour shows up as a failing test. The tests describe the code as it is, including its oddities.

## Inputs
- TARGET: the module or functions about to be changed.
- REPOSITORY CONTEXT: callers of the target, existing tests, sample data.

## Steps
1. List the public entry points of the target and who calls them. These are what you pin; private helpers are covered through them.
2. For each entry point choose representative inputs: a typical case, an empty or minimal one, a boundary, and an invalid one.
3. Run the code and record what it actually returns or raises. Write the observed value into the assertion. Do not correct what looks wrong: if the code returns an odd value, pin the odd value and add a comment `# characterised: current behaviour, may be a bug`.
4. Cover error paths: pin the exception type and its message prefix.
5. Keep the tests deterministic: no network, no wall clock, fixed random seeds, `tmp_path` for files. If the code depends on time or randomness, pass fixed values through its parameters.
6. Name tests `test_characterise_<behaviour>` and keep one behaviour per test so a failure says what changed.
7. Run the new tests on the unchanged code: they must all pass. A characterisation test that fails before the refactor is a mistake in the test.
8. Do not edit the target and do not fix bugs in this step.

## Output
Test files under `tests/` (mirroring the target path) and a short list of the oddities you pinned.

## Example
```python
from shop.pricing import format_price


def test_characterise_rounds_half_up_to_two_decimals():
    assert format_price(1.005) == "1.01"


def test_characterise_negative_prices_keep_the_sign_before_the_symbol():
    # characterised: current behaviour, may be a bug
    assert format_price(-2) == "-$2.00"
```
