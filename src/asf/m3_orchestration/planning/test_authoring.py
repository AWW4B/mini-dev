# FILE: src/asf/m3_orchestration/planning/test_authoring.py
# ROLE: Writes leaf acceptance tests with the planner tier (T3) only, or local drafts gated by user approval when T3 is unavailable.
# ARCH REF: M3; p05; A-4; D-10
# OWNS: Acceptance-test authoring
# DOES NOT OWN: Running tests (M4 verification)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (IF-12 model calls)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (IF-03 decisions)
#   - imports from src/asf/m5_shared/tools/skills.py: SkillsRegistry (IF-23 skills)
#   - imports from src/asf/contracts/tasks.py: TaskNode (leaf)
#   - imports from src/asf/contracts/decisions.py: DecisionRequest (APPROVE_LOCAL_TESTS request)
#   - imports from src/asf/contracts/errors.py: ApprovalRequired, BudgetExceeded, InvalidModelOutput, ProviderUnavailable (T3 unavailable and invalid output)
#   - called by src/asf/m3_orchestration/decomposition/leaf_certifier.py: author_acceptance_tests
#   - called by tests/m3_orchestration/planning/test_test_authoring.py: author_acceptance_tests
#   - emits/consumes: raises DecisionRequest kind APPROVE_LOCAL_TESTS when the per-run switch is on and T3 is unavailable
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Request role T3 with purpose "acceptance_tests"; never T1 (A-4).
#   6. Use the write-tests-from-acceptance skill.
#   7. Use these Agent Skills (load via SkillsRegistry): skills/write-tests-from-acceptance/SKILL.md.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/planning/test_test_authoring.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/planning/test_authoring.py` and `uv run mypy src/asf/m3_orchestration/planning/test_authoring.py` are clean.

import logging
from pathlib import Path, PurePosixPath
from typing import Any, cast

from pydantic import BaseModel

from asf.contracts.decisions import DecisionRequest
from asf.contracts.errors import ApprovalRequired, BudgetExceeded, InvalidModelOutput, ProviderUnavailable
from asf.contracts.tasks import TaskNode
from asf.m5_shared.decisions.broker import DecisionBroker
from asf.m5_shared.gateway.gateway import ModelGateway
from asf.m5_shared.tools.skills import SkillsRegistry

logger = logging.getLogger(__name__)

_SKILL = "write-tests-from-acceptance"
_PROMPT = (
    "Write pytest acceptance tests for this task. Test only what the acceptance criteria and the pinned contracts say, "
    "through the public interface; do not test implementation details. One file per module under tests/, named test_*.py. "
    "Answer with JSON: {{\"files\": {{\"tests/<path>/test_<name>.py\": \"<complete file content>\"}}}}.\n\n"
    "GOAL: {goal}\nACCEPTANCE CRITERIA: {criteria}\nCONTRACTS: {contracts}\nFILES UNDER TEST: {files}\n{context}\n{skill}"
)


class _TestFiles(BaseModel):
    files: dict[str, str]


def _safe_test_path(raw: str) -> str:
    path = PurePosixPath(raw.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "tests" or not path.name.startswith("test_") or path.suffix != ".py":
        raise InvalidModelOutput(f"The model proposed an unusable test path '{raw}': tests must be relative, under tests/, named test_*.py")
    return path.as_posix()


def _skill_text(skills: SkillsRegistry | None) -> str:
    if skills is None:
        return ""
    try:
        return f"PROCEDURE:\n{skills.load_body(_SKILL)}"
    except KeyError:
        logger.warning("skill %s is not available; writing tests without it", _SKILL)
        return ""


def author_acceptance_tests(
    node: TaskNode,
    allow_local_with_approval: bool,
    *,
    gateway: ModelGateway,
    project_root: Path,
    broker: DecisionBroker | None = None,
    skills: SkillsRegistry | None = None,
    local_approved: bool = False,
    context: str = "",
) -> list[str]:
    """Return written test file paths (relative, POSIX style).

    Written by the planner tier (T3) only (A-4, never T1). When T3 is unavailable and the per-run switch is on, a local
    draft needs the user's APPROVE_LOCAL_TESTS answer first: the request goes to the DecisionBroker and ApprovalRequired is
    raised; call again with ``local_approved=True`` once it is granted.
    """
    prompt = _PROMPT.format(
        goal=node.goal,
        criteria="; ".join(node.acceptance_refs) or "(derive them from the goal)",
        contracts=", ".join(node.contract_refs) or "(none)",
        files=", ".join(node.allowed_files) or "(unspecified)",
        context=context,
        skill=_skill_text(skills),
    )

    def draft(role: str, purpose: str) -> _TestFiles:
        model = gateway.model_for(cast(Any, role), purpose=purpose, output_schema=_TestFiles)
        raw = model.invoke(prompt)
        return raw if isinstance(raw, _TestFiles) else _TestFiles.model_validate(raw if isinstance(raw, dict) else {"files": {}})

    try:
        result = draft("T3", "acceptance_tests")
    except (ProviderUnavailable, BudgetExceeded):
        if not allow_local_with_approval:
            raise
        if not local_approved:
            if broker is not None:
                broker.request(
                    DecisionRequest.model_validate(
                        {
                            "decision_id": f"dec-local-tests-{node.id}",
                            "run_id": str(node.run_id),
                            "task_id": str(node.id),
                            "kind": "approve_local_tests",
                            "requester": "asf.m3_orchestration.planning.test_authoring",
                            "question": f"The planner tier is unavailable. Allow the local model to draft acceptance tests for task {node.id}?",
                            "options": ["approve_local_drafts", "wait_for_planner"],
                            "default_on_timeout": None,
                        }
                    )
                )
            raise ApprovalRequired(f"Local drafts of the acceptance tests for task {node.id} need your approval (APPROVE_LOCAL_TESTS).") from None
        result = draft("T2", "acceptance_tests_local_draft")

    if not result.files:
        raise InvalidModelOutput("The model returned no test files")
    written: list[str] = []
    for raw_path, content in result.files.items():
        rel = _safe_test_path(raw_path)
        target = project_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(rel)
    return written
