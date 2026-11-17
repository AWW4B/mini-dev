# FILE: src/asf/m5_shared/memory/tree_rag.py
# ROLE: Beta: tree-based retrieval over memory records; a lexical or T1 navigator opens branches by their summaries.
# ARCH REF: M5; p12 Context & Memory Service; docs/architecture/MEMORY_ARCHITECTURE.md
# OWNS: The memory tree and its navigation trace
# DOES NOT OWN: Flat search (store.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/memory/lexical.py: Bm25, estimate_tokens, keywords (lexical navigator and summaries)
#   - imports from src/asf/m5_shared/memory/store.py: MemoryRecord, MemoryStore (the records the tree indexes)
#   - called by tests/m5_shared/memory/test_tree_rag.py: build_tree, TreeRetriever
#   - called by src/asf/m5_shared/memory/router.py: TreeRetriever
#   - called by src/asf/cli/commands/memory_cmd.py: TreeRetriever
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/memory/test_tree_rag.py pass on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/memory/tree_rag.py` and `uv run mypy src/asf/m5_shared/memory/tree_rag.py` are clean.

import json
import logging
import re
from typing import Any, cast

from pydantic import BaseModel, Field

from asf.m5_shared.memory.lexical import Bm25, estimate_tokens, keywords
from asf.m5_shared.memory.store import MemoryRecord, MemoryStore

logger = logging.getLogger(__name__)

_BAG_CHARS = 8000  # characters of descendant text kept per inner node for lexical scoring (bounds memory per node)
_LAYER_ORDER = {"procedural": 0, "episodic": 1, "semantic": 2, "session": 3}


class TreeNode(BaseModel):
    """A node of the memory tree. Inner nodes carry only a summary; leaves point at a stored record (data stays data)."""

    node_id: str
    title: str
    summary: str = ""
    children: list["TreeNode"] = Field(default_factory=list)
    record: MemoryRecord | None = None
    size: int = 0
    bag: str = Field(default="", exclude=True)  # descendant terms (bounded): what the lexical navigator scores

    @property
    def is_leaf(self) -> bool:
        return self.record is not None


class TraceStep(BaseModel):
    node_id: str
    opened: list[str]
    navigator: str
    scores: dict[str, float] = Field(default_factory=dict)


class TreeRetrieval(BaseModel):
    records: list[MemoryRecord]
    paths: dict[int, str]
    trace: list[TraceStep]
    tokens: int


def _segments(record: MemoryRecord, depth: int) -> list[str]:
    parts = [p for p in re.split(r"[/\\]", record.topic) if p] or ["general"]
    if len(parts) > depth:  # keep the tree shallow: deep paths collapse into their last level
        parts = [*parts[: depth - 1], "/".join(parts[depth - 1 :])]
    return [record.layer, *parts]


def build_tree(records: list[MemoryRecord], max_depth: int = 4) -> TreeNode:
    """root -> layer -> topic path -> record. Summaries are deterministic keyword digests, so building costs no model call."""
    root = TreeNode(node_id="root", title="memory")
    index: dict[str, TreeNode] = {"root": root}
    for record in records:
        parent = root
        path = "root"
        for segment in _segments(record, max_depth):
            path = f"{path}/{segment}"
            node = index.get(path)
            if node is None:
                node = TreeNode(node_id=path, title=segment)
                index[path] = node
                parent.children.append(node)
            parent = node
        parent.children.append(TreeNode(node_id=f"{path}#{record.id}", title=record.title, summary=record.text[:240], record=record, size=1))

    def summarise(node: TreeNode) -> tuple[int, list[str]]:
        if node.is_leaf:
            assert node.record is not None
            return 1, [f"{node.record.title} {node.record.text} {' '.join(node.record.tags)}"]
        size, texts = 0, []
        for child in node.children:
            n, t = summarise(child)
            size += n
            texts.extend(t)
        node.size = size
        node.summary = f"{node.title}: {size} item(s); about " + ", ".join(keywords(texts, 10))
        node.bag = " ".join(texts)[:_BAG_CHARS]
        return size, texts[:200]  # bound the text carried upward: summaries need the gist, not everything

    summarise(root)
    root.children.sort(key=lambda c: _LAYER_ORDER.get(c.title, len(_LAYER_ORDER)))
    return root


Navigator = Any  # a ModelGateway, or None for the lexical navigator


class TreeRetriever:
    """Beta: reasoning-style retrieval over the memory tree (no embeddings, no vector store).

    At each level the navigator sees only the children's titles and summaries and opens the ``beam`` most relevant
    ones; the walk ends at leaves or ``max_depth``. The lexical navigator scores summaries with BM25. The model
    navigator asks T1 to pick branches by id and falls back to the lexical choice when the answer is unusable. Every
    decision is kept in the trace, so a retrieval can be explained and replayed.
    """

    def __init__(self, store: MemoryStore, beam: int = 3, max_depth: int = 4, navigator: str = "lexical", gateway: Navigator = None) -> None:
        self.store = store
        self.beam = max(1, beam)
        self.max_depth = max(1, max_depth)
        self.navigator = navigator
        self.gateway = gateway
        self._tree: TreeNode | None = None
        self._version: tuple[int, int, float] | None = None
        self._layers: tuple[str, ...] = ()

    def tree(self, layers: list[str], scopes: list[str] | None = None) -> TreeNode:
        version = self.store.version()
        key = tuple(sorted(layers)) + tuple(sorted(scopes or ["project"]))
        if self._tree is None or self._version != version or self._layers != key:
            self._tree = build_tree(list(self.store.iter_records(layers, scopes)), self.max_depth)
            self._version, self._layers = version, key
        return self._tree

    def _choose_lexical(self, query: str, children: list[TreeNode]) -> tuple[list[TreeNode], dict[str, float]]:
        scores = Bm25(f"{c.title} {c.summary} {c.bag}" for c in children).scores(query)
        ranked = sorted(zip(children, scores, strict=True), key=lambda p: -p[1])
        chosen = [c for c, s in ranked if s > 0][: self.beam]
        return chosen, {c.node_id: round(s, 3) for c, s in ranked}

    def _choose_model(self, query: str, children: list[TreeNode]) -> list[TreeNode] | None:
        if self.gateway is None:
            return None
        menu = [{"id": i, "title": c.title, "summary": c.summary[:200]} for i, c in enumerate(children)]
        prompt = (
            f"Pick at most {self.beam} branches of a memory index that are most useful for this request. "
            'Answer with JSON {"open": [<id>, ...]} and nothing else; [] if none is relevant.\n\n'
            f"REQUEST: {query}\n\nBRANCHES:\n{json.dumps(menu, ensure_ascii=False)}"
        )
        try:
            raw: Any = self.gateway.model_for(cast(Any, "T1"), purpose="memory_navigation").invoke(prompt)
            text = raw if isinstance(raw, str) else getattr(raw, "content", raw)
            data = text if isinstance(text, dict) else json.loads(re.search(r"\{.*\}", str(text), re.DOTALL).group(0))  # type: ignore[union-attr]
            picks = [int(i) for i in data.get("open", [])][: self.beam]
            return [children[i] for i in picks if 0 <= i < len(children)]
        except Exception:  # noqa: BLE001 - the tiny model is optional; the lexical navigator decides instead
            logger.info("model navigation failed; using the lexical navigator", exc_info=True)
            return None

    def retrieve(self, query: str, layers: list[str], budget_tokens: int, scopes: list[str] | None = None) -> TreeRetrieval:
        root = self.tree(layers, scopes)
        trace: list[TraceStep] = []
        leaves: list[tuple[float, TreeNode, str]] = []
        frontier: list[tuple[TreeNode, float, int]] = [(root, 1.0, 0)]
        while frontier:
            node, weight, depth = frontier.pop(0)
            inner = [c for c in node.children if not c.is_leaf]
            leaf_children = [c for c in node.children if c.is_leaf]
            if leaf_children:  # leaves are ranked against each other, not opened one by one
                chosen_leaves, scores = self._choose_lexical(query, leaf_children)
                for leaf in chosen_leaves:
                    leaves.append((weight * scores[leaf.node_id], leaf, node.node_id))
            if not inner or depth > self.max_depth + 1:  # the tree is root -> layer -> up to max_depth topic levels
                continue
            picked = self._choose_model(query, inner) if self.navigator == "model" and len(inner) > 1 else None
            navigator = "model" if picked is not None else "lexical"
            lexical, scores = self._choose_lexical(query, inner)
            chosen = picked if picked is not None else (inner if len(inner) == 1 else lexical)  # a single branch is not a choice
            trace.append(TraceStep(node_id=node.node_id, opened=[c.node_id for c in chosen], navigator=navigator, scores=scores))
            for child in chosen:
                frontier.append((child, weight * (1 + scores.get(child.node_id, 0.0)), depth + 1))
        leaves.sort(key=lambda t: -t[0])
        out: list[MemoryRecord] = []
        paths: dict[int, str] = {}
        used = 0
        for score, leaf, parent in leaves:
            assert leaf.record is not None
            cost = estimate_tokens(f"{leaf.record.title}\n{leaf.record.text}")
            if used + cost > budget_tokens:
                continue
            out.append(leaf.record.model_copy(update={"score": score}))
            paths[int(leaf.record.id or 0)] = parent
            used += cost
        return TreeRetrieval(records=out, paths=paths, trace=trace, tokens=used)
