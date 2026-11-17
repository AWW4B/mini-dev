# FILE: tests/m5_shared/memory/test_lexical.py
# ROLE: Tests for src/asf/m5_shared/memory/lexical.py.
# ARCH REF: M5; p12 Context & Memory Service; docs/architecture/MEMORY_ARCHITECTURE.md
# OWNS: Tests of lexical
# DOES NOT OWN: Production code
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/memory/lexical.py: Bm25, terms, keywords, estimate_tokens (unit under test)
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use the tmp_path fixture or the fake_paths fixture for every filesystem location.
#   6. Use the fakes from tests/conftest.py instead of real GPUs, networks, sandboxes or model providers unless the test is marked needs_gpu, needs_network or needs_sandbox.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; real API keys; network access in unmarked tests; sleeping for timing (use the fake clock)
# ERRORS: Failures surface as pytest assertion failures.
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/memory/test_lexical.py` on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/memory/test_lexical.py` and `uv run mypy tests/m5_shared/memory/test_lexical.py` are clean.

from asf.m5_shared.memory.lexical import Bm25, estimate_tokens, keywords, terms


def test_identifiers_are_split_into_their_parts() -> None:
    found = terms("parse_config raised ConfigError in loadSettings")
    assert {"parse_config", "parse", "config", "configerror", "loadsettings", "load", "settings"} <= set(found)
    assert "in" not in found


def test_bm25_ranks_the_matching_document_first() -> None:
    scores = Bm25(["sqlite wal journal mode", "gateway retries the provider", "wal checkpoint sqlite busy timeout"]).scores("sqlite busy timeout")
    assert scores.index(max(scores)) == 2 and scores[1] == 0


def test_keywords_and_token_estimates_are_deterministic() -> None:
    assert keywords(["retry the gateway", "gateway timeout", "gateway"], 1) == ["gateway"]
    assert estimate_tokens("") == 0 and estimate_tokens("abcd" * 10) == 10
