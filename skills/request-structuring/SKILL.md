---
name: request-structuring
description: Turn a normalised prompt, documents and repo profile into a StructuredRequest with traced REQ anchors.
version: 1.0.0
allowed-tools: [read_file, search_code]
---
<!--
FILE: skills/request-structuring/SKILL.md
ROLE: Agent Skill "request-structuring": Turn a normalised prompt, documents and repo profile into a StructuredRequest with traced REQ anchors.
ARCH REF: M2; p03 Request Understanding; IF-02; D-17; IF-23
OWNS: The procedure text loaded on demand by load_skill
DOES NOT OWN: Tool permissions (policy.toml) and model routing (gateway)
CONNECTS TO (external boundaries only):
  - called by src/asf/m5_shared/tools/skills.py: indexed and loaded via SkillsRegistry.load_body("request-structuring")
  - called by src/asf/m2_request/request_understanding.py: requests this skill for role T3
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


# request-structuring

Turn a normalised prompt, extracted documents and a repository profile into one StructuredRequest. Every requirement must be traceable to a place in the sources.

## Inputs
- PROMPT: the user's cleaned request.
- DOCUMENTS: Markdown of attached documents, split into sections with ids such as `system-architecture`.
- REPO PROFILE (optional): languages, build and test commands, baseline test results.

## Steps
1. Read the whole prompt and every document section once before writing anything.
2. Decide the task type: `new_build` (nothing exists yet), `debug` (something that exists is wrong), `feature` (add behaviour to existing code), `refactor` (same behaviour, better structure), `test_generation`, `code_docs`, or `unsupported` (not software work). When the repository profile exists, "build a new X" is usually a `feature`.
3. List requirements. One requirement is one testable statement ("users can reset their password by email"), not a topic. Give each an id: keep an id the source already uses (`REQ-4`); otherwise number them `REQ-1`, `REQ-2` in reading order. Set `source_ref` to `prompt` or to the document and section it came from.
4. Put everything that limits the solution in `constraints` (language, libraries, platforms, deadlines) and every quality target in `nfrs` (speed, memory, security, accessibility), each with its number if the source gives one.
5. Write `acceptance` as observable checks a person could run ("the login page rejects a wrong password with a message").
6. Write what you had to assume in `assumptions`. Write what you could not decide in `open_questions`. Never resolve an ambiguity silently: an invented answer is worse than an open question.
7. Check: every sentence of the sources that states a need appears in some requirement; no requirement has no source; no id repeats.

## Output
One JSON object: `request_id`, `project_id`, `task_type`, `requirements` (list of `{req_id, text, source_ref}`), `constraints`, `nfrs`, `acceptance`, `assumptions`, `open_questions`. No prose around it.

## Example
Prompt: "Build a CLI todo app. Tasks need tags. Must run on Windows and Linux, startup under one second."
```json
{"task_type": "new_build",
 "requirements": [
  {"req_id": "REQ-1", "text": "The user can add, list and complete tasks from the command line", "source_ref": "prompt"},
  {"req_id": "REQ-2", "text": "A task can carry tags and tasks can be listed by tag", "source_ref": "prompt"}],
 "constraints": ["Runs on Windows and Linux"],
 "nfrs": ["Startup time under one second"],
 "acceptance": ["`todo add 'x' --tag home` then `todo list --tag home` shows x"],
 "assumptions": ["Tasks are stored in a local file"],
 "open_questions": ["Should completed tasks be hidden by default?"]}
```
