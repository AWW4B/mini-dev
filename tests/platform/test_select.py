# FILE: tests/platform/test_select.py
# ROLE: Tests that prove src/asf/platform/select.py meets its DONE WHEN conditions.
# ARCH REF: FR-4; D-20; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/platform/select.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/platform/select.py: get_platform (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/platform/test_select.py` on Windows and Linux once src/asf/platform/select.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/platform/test_select.py` and `uv run mypy tests/platform/test_select.py` are clean.


import sys

import pytest

from asf.platform.select import get_platform


def test_get_platform_meets_contract() -> None:
    """Prove get_platform behaves as declared in src/asf/platform/select.py."""
    p1 = get_platform()
    p2 = get_platform()
    assert p1 is p2
    assert p1.name in ("windows", "linux", "fallback")
    if sys.platform == "win32":
        assert p1.name == "windows"
    elif sys.platform.startswith("linux"):
        assert p1.name == "linux"


def test_get_platform_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prove get_platform falls back to FallbackPlatform on other OSes."""
    get_platform.cache_clear()
    monkeypatch.setattr(sys, "platform", "darwin")
    p = get_platform()
    assert p.name == "fallback"
    get_platform.cache_clear()
