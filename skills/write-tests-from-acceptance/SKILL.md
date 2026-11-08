---
name: write-tests-from-acceptance
description: Write pytest acceptance tests for a leaf from its acceptance criteria and pinned capsules. Planner tier only.
version: 0.0.1
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

Stub. Write the procedure here: inputs, numbered steps, output format, one example.
