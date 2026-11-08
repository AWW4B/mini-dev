# FILE: src/asf/m3_orchestration/decomposition/rubric.py
# ROLE: T1 rubric: ambiguity and coupling scores for a node (JSON schema output).
# ARCH REF: M3; p05 T1 rubric; D-09 tiny-model tasks
# OWNS: Rubric scoring
# DOES NOT OWN: Deciding the split
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (IF-12 model calls)
#   - imports from src/asf/contracts/tasks.py: TaskNode (node)
#   - called by src/asf/m3_orchestration/decomposition/decomposition_graph.py: score_node
#   - called by tests/m3_orchestration/decomposition/test_rubric.py: RubricScore, score_node
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/decomposition/test_rubric.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/decomposition/rubric.py` and `uv run mypy src/asf/m3_orchestration/decomposition/rubric.py` are clean.

from pydantic import BaseModel

from asf.contracts.tasks import TaskNode


class RubricScore(BaseModel):
    ambiguity: float
    coupling: float
    notes: str


def score_node(node: TaskNode) -> RubricScore:
    raise NotImplementedError
