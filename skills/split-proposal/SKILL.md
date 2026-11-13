---
name: split-proposal
description: Propose a split of one task node into children with contracts and dependencies that pass split validation.
version: 1.0.0
allowed-tools: [read_file, search_code]
---
<!--
FILE: skills/split-proposal/SKILL.md
ROLE: Agent Skill "split-proposal": Propose a split of one task node into children with contracts and dependencies that pass split validation.
ARCH REF: M3; p05; A-1; A-2; D-17; IF-23
OWNS: The procedure text loaded on demand by load_skill
DOES NOT OWN: Tool permissions (policy.toml) and model routing (gateway)
CONNECTS TO (external boundaries only):
  - called by src/asf/m5_shared/tools/skills.py: indexed and loaded via SkillsRegistry.load_body("split-proposal")
  - called by src/asf/m3_orchestration/decomposition/splitter.py: requests this skill for role T3
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


# split-proposal

Split one task node into smaller children that pass the split validator. A split that fails validation is sent back, so read the rules before proposing.

## Inputs
- PARENT: goal, acceptance criteria, owned files, contract references, dependencies.
- FEEDBACK (on a retry): the validator's list of problems, or the evidence of a failed attempt.

## Rules the validator enforces
- 2 to 5 children (never 1; more than 8 is rejected).
- Every acceptance criterion of the parent appears in exactly the children that implement it; none is dropped.
- Each child owns files that no sibling owns, and every file is one the parent owns.
- Child dependencies point at siblings by position (`1` is the first child). They must not form a cycle.
- Each child is clearly smaller than the parent (at most 80 percent of its size).
- No two children have the same goal.

## Steps
1. Read the parent's acceptance criteria and group them by the files that must change to satisfy them.
2. Cut along file and interface boundaries first, not along time ("first half / second half" is a bad cut). One module or one operation per child is the usual size.
3. If two children need the same type or helper, make that its own first child and let the others depend on it (shared types are early leaves).
4. Give each child: a goal that says what is delivered in one sentence, the files it owns, its slice of the contract (`module@version` references), the acceptance criteria it covers, and the positions of the siblings it depends on.
5. Order the children so dependencies come first. Check for cycles by walking every `deps` list.
6. When FEEDBACK is present, change only what it names; keep the rest of the split as it was.

## Output
One JSON object and nothing else:
`{"children": [{"goal": "...", "allowed_files": ["..."], "contract_refs": ["..."], "acceptance_refs": ["..."], "deps": [1]}], "new_contract_ids": [], "rationale": "one sentence"}`

## Example
Parent: "Billing module" owning `src/charge.py`, `src/refund.py`, criteria "charge works", "refund works".
```json
{"children": [
  {"goal": "Implement charging", "allowed_files": ["src/charge.py"], "contract_refs": ["billing@1.0.0"], "acceptance_refs": ["charge works"], "deps": []},
  {"goal": "Implement refunds", "allowed_files": ["src/refund.py"], "contract_refs": ["billing@1.0.0"], "acceptance_refs": ["refund works"], "deps": [1]}],
 "new_contract_ids": [], "rationale": "One child per operation; refunds reuse the charge records."}
```
