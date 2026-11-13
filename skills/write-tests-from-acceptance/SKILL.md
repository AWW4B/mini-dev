---
name: write-tests-from-acceptance
description: Write pytest acceptance tests for a leaf from its acceptance criteria and pinned capsules. Planner tier only.
version: 1.0.0
allowed-tools: [read_file, search_code]
---
<!--
FILE: skills/write-tests-from-acceptance/SKILL.md
ROLE: Agent Skill "write-tests-from-acceptance": Write pytest acceptance tests for a leaf from its acceptance criteria and pinned capsules. Planner tier only.
ARCH REF: M3; p05; A-4; D-17; IF-23
OWNS: The procedure text loaded on demand by load_skill
DOES NOT OWN: Tool permissions (policy.toml) and model routing (gateway)
CONNECTS TO (external boundaries only):
  - called by src/asf/m5_shared/tools/skills.py: indexed and loaded via SkillsRegistry.load_body("write-tests-from-acceptance")
  - called by src/asf/m3_orchestration/planning/test_authoring.py: requests this skill for role T3
  - emits/consumes: none
INSTRUCTIONS (strict, imperative):
  1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
  2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
  3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
  4. Open text files with encoding="utf-8" explicitly.
  5. Keep the frontmatter first (Agent Skills format) and the body under 400 lines; skills validate warns above the configured size.
  6. Write the procedure as numbered steps with one worked example; no model names, no absolute paths. Never used by tier T1 or T2 (A-4).
FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
DONE WHEN: (1) `uv run python scripts/check_headers.py` reports no problem for this file.
-->


# write-tests-from-acceptance

Write pytest acceptance tests for one leaf task. Only the planning tier writes these: the tests are the definition of done that the coding model is judged by, so a weak model must never author them.

## Inputs
- GOAL and ACCEPTANCE CRITERIA of the leaf.
- CONTRACTS: the pinned signatures of the interfaces the leaf implements or uses (never their implementations).
- FILES UNDER TEST: the module paths the leaf will create or change.

## Steps
1. Turn each acceptance criterion into at least one test. A criterion with several outcomes ("rejects empty input and oversized input") becomes several tests.
2. Test through the public interface named in the contract. Import the module the way a user of it would; never reach into private names.
3. Name each test after the behaviour: `test_refund_returns_a_receipt`, not `test_1`.
4. Cover the error cases the contract lists (`raises LedgerError` means a `pytest.raises` test) and the edges of every input (empty, one item, the limit, one past the limit).
5. Keep tests deterministic: no network, no sleeping, no wall-clock dependence, no random values without a fixed seed. Use `tmp_path` for files.
6. Do not mock the module under test. Fake only things outside it (a clock, a remote service) and only through the parameters the contract gives you.
7. Put every file under `tests/`, named `test_<module>.py`, mirroring the source path. One file per module.
8. Read the tests once as the coding model: could a wrong implementation pass them? If yes, add the missing assertion.

## Output
One JSON object and nothing else: `{"files": {"tests/billing/test_refund.py": "<complete file content>"}}`.

## Example
Criterion: "refund returns a receipt and refuses amounts above the charge".
```python
import pytest
from billing.refund import RefundError, refund


def test_refund_returns_a_receipt():
    receipt = refund(charge_id="c1", amount=5)
    assert receipt.amount == 5 and receipt.charge_id == "c1"


def test_refund_refuses_more_than_the_charge():
    with pytest.raises(RefundError):
        refund(charge_id="c1", amount=10_000)
```
