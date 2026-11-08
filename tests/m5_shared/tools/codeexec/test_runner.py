# FILE: tests/m5_shared/tools/codeexec/test_runner.py
# ROLE: Tests that prove src/asf/m5_shared/tools/codeexec/runner.py meets its DONE WHEN conditions.
# ARCH REF: M5; p12; D-19; D-19a; D-21 (never tier B/C); D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/tools/codeexec/runner.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/tools/codeexec/runner.py: CodeExecResult, execute_code (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/tools/codeexec/test_runner.py` on Windows and Linux once src/asf/m5_shared/tools/codeexec/runner.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/tools/codeexec/test_runner.py` and `uv run mypy tests/m5_shared/tools/codeexec/test_runner.py` are clean.

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from asf.m5_shared.tools.codeexec.runner import CodeExecResult, execute_code


def test_code_exec_result_meets_contract() -> None:
    """Prove CodeExecResult behaves as declared in src/asf/m5_shared/tools/codeexec/runner.py."""
    res = CodeExecResult(
        ok=True,
        summary="Script ran fine",
        stdout_ref="all good",
        stderr_ref=None,
        tool_calls=2,
        duration_ms=120,
    )
    assert res.ok is True
    assert res.summary == "Script ran fine"
    assert res.stdout_ref == "all good"
    assert res.stderr_ref is None
    assert res.tool_calls == 2
    assert res.duration_ms == 120


def test_execute_code_meets_contract(fake_paths: Any) -> None:
    """Prove execute_code behaves as declared in src/asf/m5_shared/tools/codeexec/runner.py."""
    _ = fake_paths

    fake_executor = MagicMock()
    fake_executor.registry.specs_for.return_value = []

    # 1. Non-tier A sandbox raises error
    fake_platform_b = MagicMock()
    fake_platform_b.sandbox.return_value = SimpleNamespace(tier="B")

    with patch("asf.m5_shared.tools.codeexec.runner.get_platform", return_value=fake_platform_b):
        with pytest.raises(Exception, match="requires sandbox tier A"):
            execute_code(
                executor=fake_executor,
                script="print('hello')",
                role="T3",
                task_id="t1",
                allowed_files=[],
            )

    # 2. Tier A sandbox runs successfully
    fake_platform_a = MagicMock()
    fake_sandbox_a = MagicMock()
    fake_sandbox_a.tier = "A"
    fake_proc_result = SimpleNamespace(
        exit_code=0,
        stdout=b"Execution completed\n",
        stderr=b"",
        timed_out=False,
        duration_ms=15,
    )
    fake_sandbox_a.run.return_value = fake_proc_result
    fake_platform_a.sandbox.return_value = fake_sandbox_a

    with patch("asf.m5_shared.tools.codeexec.runner.get_platform", return_value=fake_platform_a):
        result = execute_code(
            executor=fake_executor,
            script="import tools\nprint('hello')",
            role="T3",
            task_id="t1",
            allowed_files=[],
        )
        assert result.ok is True
        assert "Execution completed" in (result.stdout_ref or "")
        assert result.tool_calls == 0
        assert result.duration_ms >= 0
