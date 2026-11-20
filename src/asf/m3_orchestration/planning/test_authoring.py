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
#   - called by src/asf/m3_orchestration/run_graph.py: author_acceptance_tests
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
    "Every requirement id in the criteria (REQ-004 and the like) must appear, as a comment or in a test name, next to the test that covers it: "
    "the final traceability check looks for the id text in the test files. "
    "Answer with JSON: {{\"files\": [{{\"path\": \"tests/<path>/test_<name>.py\", \"content\": \"<complete file content>\"}}]}}.\n\n"
    "GOAL: {goal}\nACCEPTANCE CRITERIA: {criteria}\nCONTRACTS: {contracts}\nFILES UNDER TEST (do not write or copy these; only test them): {files}\n"
    "Import the code under test the way a user would: {imports} (a root conftest.py puts the src folder on the path). Use only the names in the pinned contracts below; never invent others.\n"
    "Use exactly these keys for the test files: {targets}\n{context}\n{skill}"
)


class _TestFiles(BaseModel):
    files: dict[str, str]


class _TestFile(BaseModel):
    path: str
    content: str


class _TestFilesWire(BaseModel):
    """What the model is asked to return. A list of {path, content} objects, not a dict keyed by path: with a free-form dict the
    strict json_schema form is refused (400) and the tool-calling form made the planner model answer with the module under test
    (key src/pkg/core.py, empty body) instead of tests, while a plain-text answer to the same prompt was correct."""

    files: list[_TestFile]


def _as_files(raw: Any) -> _TestFiles:
    """Accept the wire model, a dict with a list of {path, content}, or the older dict keyed by path."""
    files = raw.get("files") if isinstance(raw, dict) else getattr(raw, "files", None)
    if isinstance(files, dict):
        return _TestFiles(files={str(k): str(v) for k, v in files.items()})
    collected: dict[str, str] = {}
    for item in files or []:
        path = item.get("path") if isinstance(item, dict) else getattr(item, "path", None)
        content = item.get("content") if isinstance(item, dict) else getattr(item, "content", "")
        if path:
            collected[str(path)] = str(content or "")
    return _TestFiles(files=collected)


MAX_REASKS = 2


def _target_names(node: TaskNode) -> list[str]:
    """The test file names asked for: one tests/test_<module>.py per file under test.

    Naming them stopped the planner model answering with the module under test (key src/pkg/core.py, body "# Placeholder") instead of tests.
    """
    modules = [PurePosixPath(f.replace(chr(92), "/")) for f in node.allowed_files]
    # a file that is already a test (tests/test_core.py) is what a worker writes, not a module under test: no tests/test_test_core.py
    names = [f"tests/test_{m.stem}.py" for m in modules if m.suffix == ".py" and m.parts[0] != "tests" and not m.stem.startswith("test_")]
    return list(dict.fromkeys(names)) or ["tests/test_<name>.py"]


def _import_lines(node: TaskNode) -> list[str]:
    """How a test imports each module under test: src/wordfreq/core.py is `import wordfreq.core` (src is on the path through conftest.py)."""
    lines = []
    for raw in node.allowed_files:
        path = PurePosixPath(raw.replace(chr(92), "/"))
        if path.suffix != ".py" or path.name == "__init__.py" or path.parts[0] == "tests":
            continue
        parts = path.with_suffix("").parts
        lines.append("from " + ".".join(parts[1:] if parts[0] == "src" else parts) + " import <name from the contract>")
    return lines


_CONFTEST = """import sys
from pathlib import Path

# generated tests import the project like a user does; the src layout and the project root are made importable here
for _folder in (Path(__file__).parent / "src", Path(__file__).parent):
    if str(_folder) not in sys.path:
        sys.path.insert(0, str(_folder))
"""


def _ensure_conftest(project_root: Path) -> None:
    """Write the root conftest.py once: without it `from wordfreq.core import ...` fails at collection in a src layout."""
    target = project_root / "conftest.py"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_CONFTEST, encoding="utf-8")


def _is_safe_test_path(raw: str) -> bool:
    try:
        _safe_test_path(raw)
    except InvalidModelOutput:
        return False
    return True


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
        targets=", ".join(_target_names(node)),
        imports="; ".join(_import_lines(node)) or "import the module by its package path",
        context=context,
        skill=_skill_text(skills),
    )

    def draft(role: str, purpose: str, ask: str = prompt) -> _TestFiles:
        model = gateway.model_for(cast(Any, role), purpose=purpose, output_schema=_TestFilesWire)
        raw = model.invoke(ask)
        return _as_files(raw)

    role, purpose = "T3", "acceptance_tests"
    try:
        result = draft(role, purpose)
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
        role, purpose = "T2", "acceptance_tests_local_draft"
        result = draft(role, purpose)

    # A model sometimes lists a source file (src/pkg/core.py) beside its tests; one bad path used to abort the whole run. Re-ask with
    # the paths that were refused (at most twice), then keep the usable files and drop the rest.
    for _ in range(MAX_REASKS):
        refused = [path for path in result.files if not _is_safe_test_path(path)]
        if result.files and not refused:
            break
        feedback = f"{prompt}\n\nYour previous answer used unusable paths {refused or '(no files at all)'}. Every key must be tests/<name>/test_<name>.py; do not include source files."
        result = draft(role, purpose, feedback)
    usable = {path: content for path, content in result.files.items() if _is_safe_test_path(path)}
    if len(usable) != len(result.files):
        logger.warning("dropped unusable test paths from the model's answer: %s", [path for path in result.files if path not in usable])
    if not usable:
        raise InvalidModelOutput("The model returned no usable test files (they must be under tests/ and named test_*.py)")
    _ensure_conftest(project_root)
    written: list[str] = []
    for raw_path, content in usable.items():
        rel = _safe_test_path(raw_path)
        target = project_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(rel)
    return written
