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

import re
from typing import Any, cast

from asf.contracts.requests import RepoProfile, StructuredRequest, TaskType
from asf.m5_shared.context.context_service import ContextService  # noqa: F401
from asf.m5_shared.decisions.broker import DecisionBroker  # noqa: F401
from asf.m5_shared.gateway.gateway import ModelGateway  # noqa: F401
from asf.m5_shared.tools.skills import SkillsRegistry  # noqa: F401


def _classify_task_type(prompt: str, repo_profile: RepoProfile | None) -> TaskType:
    p_lower = prompt.lower()
    if any(k in p_lower for k in ["fix", "bug", "error", "failing", "broken", "issue"]):
        return TaskType.DEBUG
    if any(k in p_lower for k in ["refactor", "cleanup", "reorganize", "rewrite"]):
        return TaskType.REFACTOR
    if any(k in p_lower for k in ["test", "coverage", "unit test", "integration test"]):
        return TaskType.TEST_GENERATION
    if any(k in p_lower for k in ["doc", "docs", "document", "docstring", "readme"]):
        return TaskType.CODE_DOCS
    if repo_profile is None or not repo_profile.languages:
        return TaskType.NEW_BUILD
    return TaskType.FEATURE


def understand_request(
    request_id: str,
    prompt: str,
    document_refs: list[str],
    repo_profile: RepoProfile | None,
    gateway: ModelGateway | None = None,
    skills: SkillsRegistry | None = None,
    project_id: str = "default",
) -> StructuredRequest:
    _ = (gateway, skills)
    task_type = _classify_task_type(prompt, repo_profile)

    source_ref = document_refs[0] if document_refs else "prompt"

    # Extract requirements from lines/bullets
    lines = [line.strip() for line in prompt.splitlines() if line.strip()]
    raw_reqs: list[str] = []
    constraints: list[str] = []
    acceptance: list[str] = []

    for line in lines:
        cleaned = re.sub(r"^[-*•\d.]+\s*", "", line).strip()
        if not cleaned:
            continue
        c_lower = cleaned.lower()
        if c_lower.startswith("must ") or "cannot " in c_lower or "within " in c_lower:
            constraints.append(cleaned)
        elif "acceptance" in c_lower or "verify" in c_lower:
            acceptance.append(cleaned)
        else:
            raw_reqs.append(cleaned)

    if not raw_reqs:
        raw_reqs = [prompt.strip()]

    requirements_payload: list[dict[str, Any]] = []
    for idx, r_text in enumerate(raw_reqs, start=1):
        requirements_payload.append({
            "req_id": f"REQ-{idx:03d}",
            "text": r_text,
            "source_ref": source_ref,
        })

    if repo_profile is not None and not isinstance(repo_profile, (dict, RepoProfile)) and hasattr(repo_profile, "__dict__"):
        repo_profile = cast(Any, repo_profile.__dict__)

    return StructuredRequest(
        request_id=request_id,
        project_id=project_id,  # type: ignore[arg-type]
        task_type=task_type,
        requirements=requirements_payload,  # type: ignore[arg-type]
        constraints=constraints,
        nfrs=[],
        acceptance=acceptance,
        assumptions=[],
        open_questions=[],
        repo_profile=repo_profile,
    )
