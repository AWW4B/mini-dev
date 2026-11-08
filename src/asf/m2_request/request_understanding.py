# FILE: src/asf/m2_request/request_understanding.py
# ROLE: Turns the normalised prompt, documents and repo profile into a StructuredRequest (IF-02) with traced REQ anchors.
# ARCH REF: M2; p03 Request Understanding; IF-02; IF-03 clarify
# OWNS: StructuredRequest construction
# DOES NOT OWN: Planning (M3)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/requests.py: StructuredRequest, RepoProfile, TaskType (IF-02)
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (IF-12 model calls)
#   - imports from src/asf/m5_shared/context/context_service.py: ContextService (IF-11 ContextPack)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (IF-03 decisions)
#   - imports from src/asf/m5_shared/tools/skills.py: SkillsRegistry (IF-23 skills)
#   - called by src/asf/m2_request/pipeline.py: understand_request
#   - called by tests/m2_request/test_request_understanding.py: understand_request
#   - emits/consumes: raises DecisionRequest kind CLARIFY for blocking open questions
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use the request-structuring skill; output via structured output (json_schema).
#   6. Every requirement keeps a source_ref.
#   7. Use these Agent Skills (load via SkillsRegistry): skills/request-structuring/SKILL.md.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m2_request/test_request_understanding.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m2_request/request_understanding.py` and `uv run mypy src/asf/m2_request/request_understanding.py` are clean.

from asf.contracts.requests import RepoProfile, StructuredRequest


def understand_request(request_id: str, prompt: str, document_refs: list[str], repo_profile: RepoProfile | None) -> StructuredRequest:
    raise NotImplementedError
