# FILE: tests/m5_shared/tools/test_registry.py
# ROLE: Tests that prove src/asf/m5_shared/tools/registry.py meets its DONE WHEN conditions.
# ARCH REF: M5; p12 Tools Registry; D-16; D-19 one source of truth; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/tools/registry.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/tools/registry.py: ToolRegistry (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/tools/test_registry.py` on Windows and Linux once src/asf/m5_shared/tools/registry.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/tools/test_registry.py` and `uv run mypy tests/m5_shared/tools/test_registry.py` are clean.


from types import SimpleNamespace

import pytest

from asf.m5_shared.tools.registry import ToolRegistry


def test_tool_registry_meets_contract() -> None:
    """Prove ToolRegistry behaves as declared in src/asf/m5_shared/tools/registry.py."""
    reg = ToolRegistry()

    def dummy_fn(x: int) -> int:
        return x * 2

    spec1 = SimpleNamespace(
        name="tool_one",
        description="A first tool",
        args_schema={"type": "object", "properties": {"x": {"type": "integer"}}},
        destructive=False,
        needs_network=False,
        roles=["developer", "coder"],
        source="builtin",
    )

    spec2 = SimpleNamespace(
        name="tool_two",
        description="A second tool",
        args_schema={"type": "object"},
        destructive=True,
        needs_network=True,
        roles=["admin"],
        source="builtin",
    )

    # 1. Register tools
    reg.register(spec1, dummy_fn)  # type: ignore[arg-type]
    reg.register(spec2, lambda: "ok")  # type: ignore[arg-type]

    # 2. Get tool
    ret_spec, ret_fn = reg.get("tool_one")
    assert ret_spec == spec1
    assert ret_fn(5) == 10

    # 3. Get nonexistent raises KeyError
    with pytest.raises(KeyError, match="not found"):
        reg.get("missing_tool")

    # 4. specs_for role
    dev_specs = reg.specs_for("developer")
    assert len(dev_specs) == 1
    assert dev_specs[0].name == "tool_one"

    admin_specs = reg.specs_for("admin")
    assert len(admin_specs) == 1
    assert admin_specs[0].name == "tool_two"

    empty_specs = reg.specs_for("reviewer")
    assert len(empty_specs) == 0
