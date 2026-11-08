# FILE: src/asf/m5_shared/gateway/tokenizers.py
# ROLE: Counts tokens for a target model: llama-server /tokenize, tiktoken, or a flagged estimate.
# ARCH REF: M5; p11; p12; D-31
# OWNS: Token counting
# DOES NOT OWN: Choosing context contents
# CONNECTS TO (external boundaries only):
#   - called by src/asf/m5_shared/context/context_service.py: count_tokens
#   - called by src/asf/m3_orchestration/decomposition/sizer.py: count_tokens
#   - called by tests/m5_shared/gateway/test_tokenizers.py: count_tokens
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/gateway/test_tokenizers.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/gateway/tokenizers.py` and `uv run mypy src/asf/m5_shared/gateway/tokenizers.py` are clean.

import tiktoken


def count_tokens(model_id: str, text: str) -> tuple[int, bool]:
    """Return (tokens, estimated)."""
    if not text:
        return 0, False

    try:
        enc = tiktoken.encoding_for_model(model_id)
        return len(enc.encode(text)), False
    except (KeyError, Exception):
        # Flagged estimate (~4 characters per token)
        return max(1, len(text) // 4), True
