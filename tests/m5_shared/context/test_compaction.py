# FILE: tests/m5_shared/context/test_compaction.py
# ROLE: Tests that prove src/asf/m5_shared/context/compaction.py meets its DONE WHEN conditions.
# ARCH REF: M5; p12; D-09 tiny-model tasks; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/context/compaction.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/context/compaction.py: compact_history (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/context/test_compaction.py` on Windows and Linux once src/asf/m5_shared/context/compaction.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/context/test_compaction.py` and `uv run mypy tests/m5_shared/context/test_compaction.py` are clean.

from types import SimpleNamespace
from unittest.mock import MagicMock

from asf.m5_shared.context.compaction import compact_history


def test_compact_history_meets_contract() -> None:
    """Prove compact_history behaves as declared in src/asf/m5_shared/context/compaction.py."""
    fake_gateway = MagicMock()
    fake_model = MagicMock()
    fake_gateway.model_for.return_value = fake_model
    fake_model.invoke.return_value = SimpleNamespace(content="Summarized turns content")

    # 1. Empty turns
    assert compact_history(fake_gateway, [], budget_tokens=50) == ""

    # 2. Single turn
    assert compact_history(fake_gateway, ["Only turn"], budget_tokens=50) == "Only turn"

    # 3. Multiple turns compacts via T1 model
    summary = compact_history(fake_gateway, ["Turn 1", "Turn 2", "Turn 3"], budget_tokens=50)
    assert summary == "Summarized turns content"
    fake_gateway.model_for.assert_called_with("T1", purpose="compaction")

    # 4. Graceful fallback on model failure
    fake_model.invoke.side_effect = RuntimeError("Provider down")
    fallback = compact_history(fake_gateway, ["Turn A", "Turn B"], budget_tokens=20)
    assert "Turn A" in fallback
