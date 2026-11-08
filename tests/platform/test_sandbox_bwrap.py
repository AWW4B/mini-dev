# FILE: tests/platform/test_sandbox_bwrap.py
# ROLE: Tests that prove src/asf/platform/sandbox_bwrap.py meets its DONE WHEN conditions.
# ARCH REF: D-20; D-21 tier A; D-22 network off; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/platform/sandbox_bwrap.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/platform/sandbox_bwrap.py: BubblewrapSandbox (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/platform/test_sandbox_bwrap.py` on Windows and Linux once src/asf/platform/sandbox_bwrap.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/platform/test_sandbox_bwrap.py` and `uv run mypy tests/platform/test_sandbox_bwrap.py` are clean.

from pathlib import Path

import pytest

from asf.platform.sandbox_bwrap import BubblewrapSandbox


def test_bubblewrap_sandbox_attributes() -> None:
    sandbox = BubblewrapSandbox()
    assert sandbox.name == "bubblewrap"
    assert sandbox.tier == "A"
    assert isinstance(sandbox.available(), bool)


def test_bubblewrap_build_argv(tmp_path: Path) -> None:
    sandbox = BubblewrapSandbox()

    class DummySpec:
        argv = ["echo", "hi"]
        cwd = tmp_path
        writable_paths: list[Path] = [tmp_path / "write"]
        readable_paths: list[Path] = [tmp_path / "read"]
        network = False
        timeout_s = 10
        env: dict[str, str] = {}
        extra_fds: list[int] = []

    argv = sandbox.build_argv(DummySpec())  # type: ignore[arg-type]
    assert "--die-with-parent" in argv
    assert "--unshare-all" in argv
    assert "--chdir" in argv
    assert str(tmp_path) in argv
    assert "--ro-bind" in argv
    assert "--bind" in argv
    assert "echo" in argv
    assert "hi" in argv


@pytest.mark.linux_only
@pytest.mark.needs_sandbox
def test_bubblewrap_sandbox_meets_contract(tmp_path: Path) -> None:
    """Prove BubblewrapSandbox behaves as declared in src/asf/platform/sandbox_bwrap.py."""
    sandbox = BubblewrapSandbox()
    if not sandbox.available():
        pytest.skip("bwrap not available on PATH")

    class DummySpec:
        argv = ["echo", "bwrap_ok"]
        cwd = tmp_path
        writable_paths: list[Path] = [tmp_path]
        readable_paths: list[Path] = [tmp_path]
        network = False
        timeout_s = 10
        env: dict[str, str] = {}
        extra_fds: list[int] = []

    res = sandbox.run(DummySpec())  # type: ignore[arg-type]
    assert res.exit_code == 0
    assert b"bwrap_ok" in res.stdout
