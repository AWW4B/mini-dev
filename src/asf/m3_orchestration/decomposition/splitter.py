# FILE: src/asf/m3_orchestration/decomposition/splitter.py
# ROLE: Asks the planner tier for a split proposal (children, contracts, deps) using the split-proposal skill.
# ARCH REF: M3; p05 split proposal; A-1; A-2
# OWNS: Split proposal generation
# DOES NOT OWN: Validating proposals (split_validator.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (IF-12 model calls)
#   - imports from src/asf/m5_shared/context/context_service.py: ContextService (IF-11 ContextPack)
#   - imports from src/asf/m5_shared/tools/skills.py: SkillsRegistry (IF-23 skills)
#   - imports from src/asf/contracts/tasks.py: TaskNode (node)
#   - imports from src/asf/contracts/errors.py: InvalidModelOutput (the planner kept answering badly)
#   - called by src/asf/m3_orchestration/decomposition/split_validator.py: SplitProposal
#   - called by src/asf/m3_orchestration/decomposition/decomposition_graph.py: propose_split
#   - called by tests/m3_orchestration/decomposition/test_splitter.py: SplitProposal, propose_split
#   - called by tests/m3_orchestration/decomposition/test_split_validator.py: SplitProposal
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use these Agent Skills (load via SkillsRegistry): skills/split-proposal/SKILL.md.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/decomposition/test_splitter.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/decomposition/splitter.py` and `uv run mypy src/asf/m3_orchestration/decomposition/splitter.py` are clean.

import hashlib
import json
import logging
from typing import Any, cast

from pydantic import BaseModel, Field, ValidationError

from asf.contracts.errors import InvalidModelOutput
from asf.contracts.tasks import TaskNode
from asf.m5_shared.context.context_service import ContextService
from asf.m5_shared.gateway.gateway import ModelGateway
from asf.m5_shared.tools.skills import SkillsRegistry

logger = logging.getLogger(__name__)

FORMAT_REPAIRS = 2
_SKILL = "split-proposal"


class SplitProposal(BaseModel):
    parent_id: str
    children: list[TaskNode]
    new_contract_ids: list[str]
    rationale: str


class _Child(BaseModel):
    goal: str
    allowed_files: list[str] = Field(default_factory=list)
    contract_refs: list[str] = Field(default_factory=list)
    acceptance_refs: list[str] = Field(default_factory=list)
    deps: list[int] = Field(default_factory=list, description="1-based positions of sibling children this one depends on")


class _SplitModel(BaseModel):
    children: list[_Child]
    new_contract_ids: list[str] = Field(default_factory=list)
    rationale: str = ""


def _normalise(goal: str) -> str:
    return " ".join(goal.lower().split())


def _idempotency_key(parent: TaskNode, child: _Child) -> str:
    """hash(parent, normalised goal, contract slice): proposing the same child twice yields the same key (duplicate guard)."""
    basis = f"{parent.id}|{_normalise(child.goal)}|{','.join(sorted(child.contract_refs))}"
    return hashlib.sha256(basis.encode()).hexdigest()[:24]


def _coerce(raw: Any) -> _SplitModel:
    if isinstance(raw, _SplitModel):
        return raw
    if isinstance(raw, dict):
        return _SplitModel.model_validate(raw)
    text = str(getattr(raw, "content", raw))
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("the reply contains no JSON object")
    return _SplitModel.model_validate(json.loads(text[start : end + 1]))


def _build_children(node: TaskNode, model: _SplitModel) -> list[TaskNode]:
    count = len(model.children)
    ids = [f"{node.id}.{i + 1}" for i in range(count)]
    nodes: list[TaskNode] = []
    for i, child in enumerate(model.children):
        sibling_deps = [ids[d - 1] for d in child.deps if 1 <= d <= count and d - 1 != i]
        nodes.append(
            TaskNode.model_validate(
                {
                    "id": ids[i],
                    "run_id": node.run_id,
                    "parent_id": node.id,
                    "kind": "composite",  # leaf or not is decided when the child is sized
                    "goal": child.goal,
                    "acceptance_refs": child.acceptance_refs,
                    "contract_refs": child.contract_refs,
                    "deps": [*sibling_deps, *(str(d) for d in node.deps)],
                    "allowed_files": child.allowed_files,
                    "priority": node.priority,
                    "state": "PROPOSED",
                    "depth": node.depth + 1,
                    "idempotency_key": _idempotency_key(node, child),
                }
            )
        )
    return nodes


def propose_split(
    node: TaskNode,
    *,
    gateway: ModelGateway,
    context: ContextService | str = "",
    skills: SkillsRegistry | None = None,
    feedback: str = "",
    role: str = "T3",
) -> SplitProposal:
    """Ask the planner tier for 2..k children (goal, contract slice, files, sibling deps).

    ``feedback`` carries the validator's problems or the failure evidence of a previous try. ``context`` is extra text for
    the prompt (a ContextService pack rendered by the caller is the usual source).
    """
    procedure = ""
    if skills is not None:
        try:
            procedure = f"PROCEDURE:\n{skills.load_body(_SKILL)}"
        except KeyError:
            logger.warning("skill %s is not available; proposing the split without it", _SKILL)
    prompt = (
        "Split this task into 2 to 5 smaller children. Each child needs a goal, the files it owns (no file may belong to two "
        "children), its slice of the contract, acceptance criteria, and the positions of the siblings it depends on. Together "
        "the children must cover every acceptance criterion of the parent and must each be smaller than the parent. "
        'Answer with JSON {"children": [{"goal": "...", "allowed_files": [], "contract_refs": [], "acceptance_refs": [], "deps": []}], '
        '"new_contract_ids": [], "rationale": "..."}.\n\n'
        f"PARENT GOAL: {node.goal}\nPARENT ACCEPTANCE: {'; '.join(node.acceptance_refs) or '(none)'}\n"
        f"PARENT FILES: {', '.join(node.allowed_files) or '(none)'}\nPARENT CONTRACTS: {', '.join(node.contract_refs) or '(none)'}\n"
        f"{context if isinstance(context, str) else ''}\n{procedure}"
    )
    if feedback:
        prompt += f"\nYOUR PREVIOUS SPLIT WAS REJECTED. Fix exactly this:\n{feedback}"

    model = gateway.model_for(cast(Any, role), purpose="split_proposal", output_schema=_SplitModel, task_id=str(node.id))
    current, problem = prompt, ""
    for _ in range(FORMAT_REPAIRS + 1):
        try:
            parsed = _coerce(model.invoke(current))
            break
        except (ValidationError, ValueError) as err:
            problem = str(err)[:1500]
            current = f"{prompt}\n\nYour previous answer was invalid: {problem}\nAnswer again with valid JSON."
    else:
        raise InvalidModelOutput(f"The planner did not return a valid split after {FORMAT_REPAIRS + 1} tries: {problem}")

    return SplitProposal(parent_id=str(node.id), children=_build_children(node, parsed), new_contract_ids=parsed.new_contract_ids, rationale=parsed.rationale)
