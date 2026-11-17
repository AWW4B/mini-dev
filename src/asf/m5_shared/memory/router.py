# FILE: src/asf/m5_shared/memory/router.py
# ROLE: Chooses which memory records and skills enter one model call, per role and layer budget, and records why.
# ARCH REF: M5; p12 Context & Memory Service; docs/architecture/MEMORY_ARCHITECTURE.md
# OWNS: Inclusion and exclusion decisions
# DOES NOT OWN: Token counting and the final pack (context/context_service.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/memory/budgets.py: LayerBudgets (per-layer budgets)
#   - imports from src/asf/m5_shared/memory/device_budget.py: pct (skill shares)
#   - imports from src/asf/m5_shared/memory/lexical.py: Bm25, estimate_tokens (skill ranking and cost)
#   - imports from src/asf/m5_shared/memory/store.py: MemoryRecord, MemoryStore (candidates)
#   - imports from src/asf/m5_shared/memory/tree_rag.py: TreeRetriever (beta retrieval)
#   - imports from src/asf/contracts/context.py: ContextItem, ContextTier (items for the ContextService)
#   - called by tests/m5_shared/memory/test_router.py: MemoryRouter, ROLE_LAYERS
#   - called by src/asf/m5_shared/memory/hooks.py: MemoryRouter, RoutedMemory
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/memory/test_router.py pass on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/memory/router.py` and `uv run mypy src/asf/m5_shared/memory/router.py` are clean.

import logging
from typing import Any

from pydantic import BaseModel, Field

from asf.contracts.context import ContextItem, ContextTier
from asf.m5_shared.memory.budgets import LayerBudgets
from asf.m5_shared.memory.device_budget import pct
from asf.m5_shared.memory.lexical import Bm25, estimate_tokens
from asf.m5_shared.memory.store import MemoryRecord, MemoryStore
from asf.m5_shared.memory.tree_rag import TreeRetriever

logger = logging.getLogger(__name__)

# Which stored layers each role may receive, in the order they are filled. T1 does narrow jobs and gets none.
ROLE_LAYERS: dict[str, tuple[str, ...]] = {
    "T1": (),
    "T2": ("procedural", "session", "semantic", "episodic"),
    "T3": ("semantic", "episodic", "procedural", "session"),
    "reviewer": ("procedural", "semantic", "episodic", "session"),
}
_TIER = {"procedural": ContextTier.P3_SNIPPETS, "semantic": ContextTier.P4_DECISIONS, "session": ContextTier.P4_DECISIONS, "episodic": ContextTier.P5_FAILURE}


class Decision(BaseModel):
    layer: str
    ref: str
    tokens: int = 0
    reason: str


class RoutedMemory(BaseModel):
    items: list[ContextItem] = Field(default_factory=list)
    included: list[Decision] = Field(default_factory=list)
    excluded: list[Decision] = Field(default_factory=list)
    record_ids: list[int] = Field(default_factory=list)

    def tokens(self, layer: str | None = None) -> int:
        return sum(d.tokens for d in self.included if layer is None or d.layer == layer)


def _item(layer: str, ref: str, text: str) -> ContextItem:
    return ContextItem(tier=_TIER.get(layer, ContextTier.P3_SNIPPETS), source_ref=ref, sha256="", tokens=0, text=text)


class MemoryRouter:
    """Chooses, for one model call, what long-term memory and which skills go into the prompt, under the role's budgets.

    Inclusion rules (each candidate must pass all of them):
      - the role may receive the layer (ROLE_LAYERS) and the layer has a budget;
      - it scores at least ``min_score_pct`` of the best match for this request;
      - it is in scope: project-wide, or this run's session;
      - it is trusted (MCP-derived records are never injected);
      - it is not already in the prompt (same content) and it fits in what is left of the layer's budget.
    Every decision is returned (included and excluded, with the reason) so a prompt can be audited.
    """

    def __init__(self, store: MemoryStore, config: dict[str, Any], skills: Any = None, gateway: Any = None) -> None:
        self.store = store
        self.config = config
        self.skills = skills
        beta = dict(config.get("beta", {}))
        self.tree: TreeRetriever | None = None
        if bool(beta.get("tree_rag", False)):
            self.tree = TreeRetriever(
                store, beam=int(beta.get("tree_beam", 3)), max_depth=int(beta.get("tree_max_depth", 4)),
                navigator=str(beta.get("tree_navigator", "lexical")), gateway=gateway,
            )

    def _candidates(self, layer: str, query: str, scopes: list[str], budget: int) -> list[MemoryRecord]:
        if self.tree is not None:
            return self.tree.retrieve(query, [layer], budget, scopes).records
        return self.store.search(query, [layer], scopes, limit=25)

    def _skills(self, query: str, role: str, budget: int, out: RoutedMemory) -> int:
        """Progressive disclosure: an index of every skill (names + descriptions), then at most ``max_bodies`` full bodies."""
        if self.skills is None or budget <= 0:
            return 0
        cfg = dict(self.config.get("skills", {}))
        manifests = list(self.skills.lookup("*", role))
        if not manifests:
            return 0
        used = 0
        index_budget = int(budget * pct(cfg, "index_pct"))
        lines = []
        for m in manifests:
            line = f"- {m.name}: {m.description}"
            if used + estimate_tokens(line) > index_budget:
                out.excluded.append(Decision(layer="procedural", ref=f"skill-index:{m.name}", reason="skill index share is full"))
                continue
            lines.append(line)
            used += estimate_tokens(line)
        if lines:
            out.items.append(_item("procedural", "skills:index", "Available skills (ask for one by name if needed):\n" + "\n".join(lines)))
            out.included.append(Decision(layer="procedural", ref="skills:index", tokens=used, reason=f"{len(lines)} skill(s) listed"))
        scores = Bm25(f"{m.name} {m.description}" for m in manifests).scores(query)
        ranked = [m for m, s in sorted(zip(manifests, scores, strict=True), key=lambda p: -p[1]) if s > 0]
        for m in ranked[: int(cfg.get("max_bodies", 2))]:
            cost = max(1, m.body_chars // 4)
            if used + cost > budget:
                out.excluded.append(Decision(layer="procedural", ref=f"skill:{m.name}", tokens=cost, reason="the full skill does not fit the procedural budget"))
                continue
            out.items.append(_item("procedural", f"skill:{m.name}", self.skills.load_body(m.name)))
            out.included.append(Decision(layer="procedural", ref=f"skill:{m.name}", tokens=cost, reason="most relevant skill for the request"))
            used += cost
        return used

    def assemble(self, role: str, query: str, budgets: LayerBudgets, run_id: str | None = None, already: set[str] | None = None) -> RoutedMemory:
        out = RoutedMemory()
        seen = set(already or ())
        for layer in ROLE_LAYERS.get(role, ()):
            budget = budgets.get(layer)
            if budget <= 0:
                continue
            used = self._skills(query, role, budget, out) if layer == "procedural" else 0
            scopes = [f"run:{run_id}"] if layer == "session" and run_id else ["project"]
            if layer == "session" and not run_id:
                continue
            for record in self._candidates(layer, query, scopes, budget - used):
                ref = f"{layer}:{record.id}"
                text = f"{record.title}\n{record.text}"
                cost = estimate_tokens(text)
                if not record.trusted:
                    out.excluded.append(Decision(layer=layer, ref=ref, tokens=cost, reason="untrusted source (MCP or web)"))
                elif record.content_hash in seen:
                    out.excluded.append(Decision(layer=layer, ref=ref, tokens=cost, reason="already in the prompt"))
                elif used + cost > budget:
                    out.excluded.append(Decision(layer=layer, ref=ref, tokens=cost, reason=f"over the {layer} budget ({budget} tokens)"))
                else:
                    seen.add(record.content_hash)
                    used += cost
                    out.items.append(_item(layer, ref, text))
                    out.included.append(Decision(layer=layer, ref=ref, tokens=cost, reason=f"relevance {record.score:.2f}"))
                    if record.id is not None:
                        out.record_ids.append(record.id)
        self.store.touch(out.record_ids)
        return out
