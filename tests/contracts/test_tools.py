# FILE: tests/contracts/test_tools.py
# ROLE: Tests that prove src/asf/contracts/tools.py meets its DONE WHEN conditions.
# ARCH REF: p12; IF-14; IF-23; D-16; D-17; D-19; D-21; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/tools.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tools.py: SandboxTier, ToolSpec, ToolInvocation, ToolResult, SkillManifest (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_tools.py` on Windows and Linux once src/asf/contracts/tools.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_tools.py` and `uv run mypy tests/contracts/test_tools.py` are clean.



import pytest
from pydantic import ValidationError

from asf.contracts.tools import SandboxTier, SkillManifest, ToolInvocation, ToolResult, ToolSpec


def test_sandbox_tiers() -> None:
    assert [t.value for t in SandboxTier] == ["A", "B", "C"]


def test_tool_spec_defaults_are_safe() -> None:
    spec = ToolSpec.model_validate({"name": "read_file", "description": "d", "args_schema": {"type": "object"}, "roles": ["worker"], "source": "builtin"})
    assert spec.destructive is False
    assert spec.needs_network is False


def test_tool_spec_requires_roles_and_source() -> None:
    data = {"name": "t", "description": "d", "args_schema": {}, "roles": [], "source": "builtin"}
    ToolSpec.model_validate(data)
    for missing in ("roles", "source", "args_schema"):
        partial = dict(data)
        del partial[missing]
        with pytest.raises(ValidationError):
            ToolSpec.model_validate(partial)


def test_invocation_defaults_and_required_workspace() -> None:
    inv = ToolInvocation.model_validate({"tool": "t", "args": {}, "role": "worker", "workspace_dir": "ws"})
    assert inv.task_id is None and inv.reason is None
    assert inv.via_code_exec is False
    with pytest.raises(ValidationError):
        ToolInvocation.model_validate({"tool": "t", "args": {}, "role": "worker"})


def test_result_sandbox_tier_is_optional_and_typed() -> None:
    base = {"tool": "t", "status": "ok", "output": "x", "duration_ms": 3}
    res = ToolResult.model_validate(base)
    assert res.sandbox_tier is None and res.exit_code is None and res.output_ref is None
    assert ToolResult.model_validate({**base, "sandbox_tier": "B"}).sandbox_tier is SandboxTier.B
    with pytest.raises(ValidationError):
        ToolResult.model_validate({**base, "sandbox_tier": "Z"})


def test_result_round_trip() -> None:
    res = ToolResult.model_validate({"tool": "t", "status": "error", "exit_code": 2, "output": "boom", "duration_ms": 9, "sandbox_tier": "A"})
    assert ToolResult.model_validate_json(res.model_dump_json()) == res


def test_skill_manifest_is_metadata_only() -> None:
    m = SkillManifest.model_validate({"name": "s", "description": "d", "version": "1", "path": "skills/s/SKILL.md", "body_chars": 120})
    assert m.allowed_tools == []
    assert m.body_chars == 120
    with pytest.raises(ValidationError):
        SkillManifest.model_validate({"name": "s", "description": "d", "version": "1", "path": "p"})
