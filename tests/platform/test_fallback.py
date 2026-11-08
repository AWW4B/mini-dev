# FILE: tests/platform/test_fallback.py
# ROLE: Tests that prove src/asf/platform/fallback.py meets its DONE WHEN conditions.
# ARCH REF: FR-4 safe fallback; D-21 tier C; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/platform/fallback.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/platform/fallback.py: FallbackPlatform, StaticOnlySandbox (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/platform/test_fallback.py` on Windows and Linux once src/asf/platform/fallback.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/platform/test_fallback.py` and `uv run mypy tests/platform/test_fallback.py` are clean.


import sys
from pathlib import Path

import pytest

from asf.platform.fallback import FallbackPlatform, StaticOnlySandbox  # noqa: F401


def test_static_only_sandbox_meets_contract(tmp_path: Path) -> None:
    """Prove StaticOnlySandbox behaves as declared in src/asf/platform/fallback.py."""
    sandbox = StaticOnlySandbox()
    assert sandbox.name == "static-only"
    assert str(sandbox.tier) == "C" or getattr(sandbox.tier, "value", str(sandbox.tier)) == "C"
    assert sandbox.available() is True

    # Any spec passed to run() must raise a SandboxUnavailable (subclass of Exception)
    with pytest.raises(Exception) as exc_info:
        sandbox.run(object())
    assert exc_info.type.__name__ == "SandboxUnavailable"


def test_fallback_platform_meets_contract(tmp_path: Path) -> None:
    """Prove FallbackPlatform behaves as declared in src/asf/platform/fallback.py."""
    platform = FallbackPlatform()
    assert platform.name == "fallback"

    # sandbox returns StaticOnlySandbox
    sb = platform.sandbox()
    assert isinstance(sb, StaticOnlySandbox)

    # run_process
    res = platform.run_process(
        [sys.executable, "-c", "import sys; sys.stdout.write('hello'); sys.exit(0)"],
        cwd=tmp_path,
        timeout_s=10,
    )
    assert res.exit_code == 0
    assert res.stdout == b"hello"
    assert res.timed_out is False
    assert res.duration_ms >= 0

    # run_process with timeout
    timeout_res = platform.run_process(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
        timeout_s=1,
    )
    assert timeout_res.timed_out is True

    # lock_file
    lock_file = tmp_path / "test.lock"
    with platform.lock_file(lock_file, timeout_s=2):  # type: ignore[attr-defined]
        assert lock_file.exists()

    # resolve_within normal path
    sub = tmp_path / "sub"
    sub.mkdir()
    resolved = platform.resolve_within(tmp_path, "sub")
    assert resolved == sub.resolve()

    # resolve_within escaping root raises
    with pytest.raises(Exception) as exc_info:
        platform.resolve_within(sub, "../outside.txt")
    assert exc_info.type.__name__ == "SandboxUnavailable"

