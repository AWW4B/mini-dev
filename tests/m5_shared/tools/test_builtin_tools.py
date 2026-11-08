# FILE: tests/m5_shared/tools/test_builtin_tools.py
# ROLE: Tests that prove src/asf/m5_shared/tools/builtin_tools.py meets its DONE WHEN conditions.
# ARCH REF: M5; p12; IF-14; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/tools/builtin_tools.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/tools/builtin_tools.py: read_file, write_file, search_code, run_tests, run_linter, register_builtin_tools (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/tools/test_builtin_tools.py` on Windows and Linux once src/asf/m5_shared/tools/builtin_tools.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/tools/test_builtin_tools.py` and `uv run mypy tests/m5_shared/tools/test_builtin_tools.py` are clean.


from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from asf.m5_shared.tools.builtin_tools import (
    read_file,
    register_builtin_tools,
    run_linter,
    run_tests,
    search_code,
    write_file,
)


def test_read_file_meets_contract(tmp_path: Path) -> None:
    """Prove read_file behaves as declared in src/asf/m5_shared/tools/builtin_tools.py."""
    f = tmp_path / "greeting.txt"
    f.write_text("Hello World", encoding="utf-8")
    content = read_file(tmp_path, "greeting.txt")
    assert content == "Hello World"


def test_write_file_meets_contract(tmp_path: Path) -> None:
    """Prove write_file behaves as declared in src/asf/m5_shared/tools/builtin_tools.py."""
    write_file(tmp_path, "nested/out.txt", "Some Data")
    created = tmp_path / "nested" / "out.txt"
    assert created.is_file()
    assert created.read_text(encoding="utf-8") == "Some Data"


def test_search_code_meets_contract(tmp_path: Path) -> None:
    """Prove search_code behaves as declared in src/asf/m5_shared/tools/builtin_tools.py."""
    f1 = tmp_path / "a.py"
    f1.write_text("def find_me():\n    pass\n", encoding="utf-8")
    f2 = tmp_path / "b.py"
    f2.write_text("other code\n", encoding="utf-8")

    results = search_code(tmp_path, "find_me")
    assert len(results) >= 1
    assert any("find_me" in r for r in results)


def test_run_tests_meets_contract(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Prove run_tests behaves as declared in src/asf/m5_shared/tools/builtin_tools.py."""
    class FakePlatform:
        @staticmethod
        def run_process(argv: list[str], cwd: Path, timeout_s: int) -> Any:
            return SimpleNamespace(
                exit_code=0,
                stdout=b"1 passed",
                stderr=b"",
                timed_out=False,
                duration_ms=15,
            )

    monkeypatch.setattr("asf.m5_shared.tools.builtin_tools.get_platform", lambda: FakePlatform())
    code, output = run_tests(tmp_path, ["tests/test_x.py"])
    assert code == 0
    assert "1 passed" in output


def test_run_linter_meets_contract(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Prove run_linter behaves as declared in src/asf/m5_shared/tools/builtin_tools.py."""
    class FakePlatform:
        @staticmethod
        def run_process(argv: list[str], cwd: Path, timeout_s: int) -> Any:
            return SimpleNamespace(
                exit_code=0,
                stdout=b"All checks passed!",
                stderr=b"",
                timed_out=False,
                duration_ms=5,
            )

    monkeypatch.setattr("asf.m5_shared.tools.builtin_tools.get_platform", lambda: FakePlatform())
    code, output = run_linter(tmp_path, ["src/"])
    assert code == 0
    assert "All checks passed!" in output


def test_register_builtin_tools_meets_contract() -> None:
    """Prove register_builtin_tools behaves as declared in src/asf/m5_shared/tools/builtin_tools.py."""
    registered: dict[str, Any] = {}

    class FakeRegistry:
        def register(self, spec: Any, fn: Any) -> None:
            registered[spec.name] = (spec, fn)

    fake_reg = FakeRegistry()
    register_builtin_tools(fake_reg)  # type: ignore[arg-type]

    assert "read_file" in registered
    assert "write_file" in registered
    assert "search_code" in registered
    assert "run_tests" in registered
    assert "run_linter" in registered
