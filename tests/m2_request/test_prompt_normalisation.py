# FILE: tests/m2_request/test_prompt_normalisation.py
# ROLE: Tests that prove src/asf/m2_request/prompt_normalisation.py meets its DONE WHEN conditions.
# ARCH REF: M2; p03 Prompt Normalisation & Optimisation; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m2_request/prompt_normalisation.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m2_request/prompt_normalisation.py: normalise_prompt (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m2_request/test_prompt_normalisation.py` on Windows and Linux once src/asf/m2_request/prompt_normalisation.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m2_request/test_prompt_normalisation.py` and `uv run mypy tests/m2_request/test_prompt_normalisation.py` are clean.

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from asf.m2_request.prompt_normalisation import normalise_prompt


def test_normalise_prompt_meets_contract() -> None:
    """Prove normalise_prompt behaves as declared in src/asf/m2_request/prompt_normalisation.py."""
    # 1. Deterministic normalization without gateway
    raw = "  Implement a feature\xa0with “smart quotes” and ‘single quotes’.  \r\n\r\n\r\n* step 1\r\n+ step 2   \n"
    norm = normalise_prompt(raw)

    assert "“" not in norm
    assert "”" not in norm
    assert "\r" not in norm
    assert "\xa0" not in norm
    assert '"smart quotes"' in norm
    assert "'single quotes'" in norm
    assert "- step 1" in norm
    assert "- step 2" in norm

    # 2. Empty input
    assert normalise_prompt("") == ""
    assert normalise_prompt("   \n\r\n  ") == ""

    # 3. Optional gateway enhancement
    fake_gateway: Any = MagicMock()
    fake_model = MagicMock()
    fake_model.invoke.return_value = SimpleNamespace(content="Optimized prompt text by T1 model")
    fake_gateway.model_for.return_value = fake_model

    enhanced = normalise_prompt("Fix the login bug", gateway=fake_gateway)
    assert enhanced == "Optimized prompt text by T1 model"
