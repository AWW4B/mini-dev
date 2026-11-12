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

import logging
import re
from typing import Any, cast

from pydantic import BaseModel, ValidationError

from asf.contracts.tasks import TaskNode
from asf.m5_shared.gateway.gateway import ModelGateway

logger = logging.getLogger(__name__)

_VAGUE = re.compile(r"\b(etc|and so on|somehow|as needed|appropriate(ly)?|tbd|maybe|something like|various|and more)\b", re.I)


class RubricScore(BaseModel):
    ambiguity: float
    coupling: float
    notes: str


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _deterministic(node: TaskNode) -> RubricScore:
    """The fallback when no tiny model is available: cheap, explainable heuristics over the node's own fields."""
    ambiguity = 0.2
    notes: list[str] = []
    if not node.acceptance_refs:
        ambiguity += 0.3
        notes.append("no acceptance criteria")
    if len(node.goal.split()) < 5:
        ambiguity += 0.2
        notes.append("very short goal")
    if _VAGUE.search(node.goal):
        ambiguity += 0.2
        notes.append("vague wording")
    coupling = 0.15 * len(node.deps) + 0.1 * len(node.contract_refs) + 0.1 * max(0, len(node.allowed_files) - 1)
    return RubricScore(ambiguity=_clamp(ambiguity), coupling=_clamp(coupling), notes="deterministic rubric: " + (", ".join(notes) or "no concerns"))


def score_node(node: TaskNode, *, gateway: ModelGateway | None = None) -> RubricScore:
    """T1 rubric: ambiguity and coupling in [0, 1] as JSON; a deterministic estimate when the model is unavailable."""
    if gateway is None:
        return _deterministic(node)
    prompt = (
        "Score this software task for a small coding model. ambiguity: 0 = precise and testable, 1 = vague or contradictory. "
        "coupling: 0 = self-contained, 1 = touches many other modules. Answer with JSON "
        '{"ambiguity": <0..1>, "coupling": <0..1>, "notes": "<one sentence>"}.\n\n'
        f"GOAL: {node.goal}\nACCEPTANCE: {'; '.join(node.acceptance_refs) or '(none)'}\n"
        f"FILES: {', '.join(node.allowed_files) or '(none)'}\nDEPENDS ON: {', '.join(map(str, node.deps)) or '(none)'}"
    )
    try:
        raw: Any = gateway.model_for(cast(Any, "T1"), purpose="rubric", output_schema=RubricScore).invoke(prompt)
        score = raw if isinstance(raw, RubricScore) else RubricScore.model_validate(raw if isinstance(raw, dict) else raw.content)
    except (ValidationError, ValueError, AttributeError):
        logger.warning("the rubric model answered outside the schema; using the deterministic rubric", exc_info=True)
        return _deterministic(node)
    except Exception:  # noqa: BLE001 - provider errors vary; the rubric is advisory
        logger.warning("the rubric model is unavailable; using the deterministic rubric", exc_info=True)
        return _deterministic(node)
    return RubricScore(ambiguity=_clamp(score.ambiguity), coupling=_clamp(score.coupling), notes=score.notes)
