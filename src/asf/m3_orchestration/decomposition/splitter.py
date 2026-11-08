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
#   - called by src/asf/m3_orchestration/decomposition/split_validator.py: SplitProposal
#   - called by src/asf/m3_orchestration/decomposition/decomposition_graph.py: propose_split
#   - called by tests/m3_orchestration/decomposition/test_splitter.py: SplitProposal, propose_split
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

from pydantic import BaseModel

from asf.contracts.tasks import TaskNode


class SplitProposal(BaseModel):
    parent_id: str
    children: list[TaskNode]
    new_contract_ids: list[str]
    rationale: str


def propose_split(node: TaskNode) -> SplitProposal:
    raise NotImplementedError
