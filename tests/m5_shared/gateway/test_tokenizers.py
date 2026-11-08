# FILE: tests/m5_shared/gateway/test_tokenizers.py
# ROLE: Tests that prove src/asf/m5_shared/gateway/tokenizers.py meets its DONE WHEN conditions.
# ARCH REF: M5; p11; p12; D-31; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/gateway/tokenizers.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/gateway/tokenizers.py: count_tokens (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/gateway/test_tokenizers.py` on Windows and Linux once src/asf/m5_shared/gateway/tokenizers.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/gateway/test_tokenizers.py` and `uv run mypy tests/m5_shared/gateway/test_tokenizers.py` are clean.

import pytest

from asf.m5_shared.gateway.tokenizers import count_tokens


def test_count_tokens_meets_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prove count_tokens behaves as declared in src/asf/m5_shared/gateway/tokenizers.py."""
    # 1. Empty text returns 0 tokens, measured (not estimated)
    tokens_empty, est_empty = count_tokens("gpt-4", "")
    assert tokens_empty == 0
    assert est_empty is False

    # 2. Known model with local fake encoder (strictly no network access)
    class FakeEncoding:
        def encode(self, text: str) -> list[int]:
            return [1] * len(text.split())

    def fake_encoding_for_model(model_name: str) -> FakeEncoding:
        if model_name == "gpt-4":
            return FakeEncoding()
        raise KeyError(model_name)

    monkeypatch.setattr("tiktoken.encoding_for_model", fake_encoding_for_model)

    sample_text = "Hello world this is a test"
    tokens_known, est_known = count_tokens("gpt-4", sample_text)
    assert tokens_known == 6
    assert est_known is False

    # 3. Unknown model falls back to flagged estimate (~4 chars per token)
    tokens_unknown, est_unknown = count_tokens("nonexistent-custom-llm", "12345678")
    assert tokens_unknown == 2
    assert est_unknown is True
