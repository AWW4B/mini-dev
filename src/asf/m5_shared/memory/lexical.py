# FILE: src/asf/m5_shared/memory/lexical.py
# ROLE: Model-free text scoring for memory: term extraction, BM25 and keyword digests.
# ARCH REF: M5; p12 Context & Memory Service; docs/architecture/MEMORY_ARCHITECTURE.md
# OWNS: Lexical scoring
# DOES NOT OWN: Storage and routing
# CONNECTS TO (external boundaries only):
#   - called by tests/m5_shared/memory/test_lexical.py: Bm25, terms, keywords, estimate_tokens
#   - called by src/asf/m5_shared/memory/store.py: Bm25, terms
#   - called by src/asf/m5_shared/memory/tree_rag.py: Bm25, estimate_tokens, keywords
#   - called by src/asf/m5_shared/memory/router.py: Bm25, estimate_tokens
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/memory/test_lexical.py pass on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/memory/lexical.py` and `uv run mypy src/asf/m5_shared/memory/lexical.py` are clean.

import math
import re
from collections import Counter
from collections.abc import Iterable

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}|\d{2,}")
_STOP = frozenset(
    "the a an and or of to in on for with is are was be by it this that as at from into not no do does use used when then than "
    "def class self return import none true false".split()
)


def terms(text: str) -> list[str]:
    """Lower-case word terms; snake_case and CamelCase identifiers are also split into their parts."""
    out: list[str] = []
    for word in _WORD.findall(text):
        lowered = word.lower()
        if lowered not in _STOP:
            out.append(lowered)
        parts = [p.lower() for p in re.split(r"_|(?<=[a-z])(?=[A-Z])", word) if len(p) > 1]
        if len(parts) > 1:
            out.extend(p for p in parts if p not in _STOP)
    return out


def estimate_tokens(text: str) -> int:
    """A fast estimate (4 characters per token). The ContextService recounts with the model's tokenizer."""
    return max(1, len(text) // 4) if text else 0


class Bm25:
    """Okapi BM25 over a small in-memory corpus (node summaries, a candidate list). k1/b are the usual defaults."""

    def __init__(self, documents: Iterable[str], k1: float = 1.2, b: float = 0.75) -> None:
        self.docs = [Counter(terms(d)) for d in documents]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        self.k1, self.b = k1, b
        df: Counter[str] = Counter()
        for doc in self.docs:
            df.update(doc.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str) -> list[float]:
        q = set(terms(query))
        out: list[float] = []
        for doc, length in zip(self.docs, self.lengths, strict=True):
            s = 0.0
            for t in q:
                f = doc.get(t, 0)
                if f:
                    s += self.idf.get(t, 0.0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * length / (self.avg or 1)))
            out.append(s)
        return out


def keywords(texts: Iterable[str], limit: int = 8) -> list[str]:
    """The most frequent terms of a group of texts: a deterministic, model-free node summary."""
    counts: Counter[str] = Counter()
    for text in texts:
        counts.update(set(terms(text)))
    return [t for t, _ in counts.most_common(limit)]
