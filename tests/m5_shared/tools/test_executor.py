# FILE: tests/m5_shared/tools/test_executor.py
# ROLE: Tests that prove src/asf/m5_shared/tools/executor.py meets its DONE WHEN conditions.
# ARCH REF: M5; p12 Tool Executor; IF-14 ToolInvocation; D-16; D-19; D-14b narrative events; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/tools/executor.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/tools/executor.py: ToolExecutor (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/tools/test_executor.py` on Windows and Linux once src/asf/m5_shared/tools/executor.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/tools/test_executor.py` and `uv run mypy tests/m5_shared/tools/test_executor.py` are clean.


from types import SimpleNamespace
from typing import Any

from langchain_core.tools import BaseTool

from asf.m5_shared.tools.executor import ToolExecutor


class FakeRegistry:
    def __init__(self) -> None:
        self.tools: dict[str, tuple[Any, Any]] = {}

    def register(self, spec: Any, fn: Any) -> None:
        self.tools[spec.name] = (spec, fn)

    def get(self, name: str) -> tuple[Any, Any]:
        return self.tools[name]

    def specs_for(self, role: str) -> list[Any]:
        return [spec for spec, _ in self.tools.values() if role in spec.roles]


class FakePolicy:
    def check(self, invocation: Any, spec: Any, tier: Any, allowed_files: list[str]) -> Any:
        if invocation.role == "denied_role":
            return SimpleNamespace(verdict=SimpleNamespace(value="deny"), reason="Role denied")
        return SimpleNamespace(verdict=SimpleNamespace(value="allow"), reason="OK")


def test_tool_executor_meets_contract(tmp_path: Any) -> None:
    """Prove ToolExecutor behaves as declared in src/asf/m5_shared/tools/executor.py."""
    reg = FakeRegistry()
    policy = FakePolicy()

    def add(a: int, b: int) -> int:
        return a + b

    spec = SimpleNamespace(
        name="add_numbers",
        description="Add two numbers",
        args_schema={"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}},
        destructive=False,
        needs_network=False,
        roles=["worker"],
        source="builtin",
    )
    reg.register(spec, add)

    executor = ToolExecutor(
        registry=reg,  # type: ignore[arg-type]
        policy=policy,  # type: ignore[arg-type]
        tier="A",  # type: ignore[arg-type]
    )

    # 1. Active tier
    assert executor.active_tier() == "A"

    # 2. Invoke allowed
    inv = SimpleNamespace(
        tool="add_numbers",
        args={"a": 3, "b": 7},
        role="worker",
        workspace_dir=str(tmp_path),
        task_id="task-1",
    )
    res = executor.invoke(inv, allowed_files=[])  # type: ignore[arg-type]
    assert res.tool == "add_numbers"
    assert res.status == "ok"
    assert res.exit_code == 0
    assert "10" in res.output
    assert res.duration_ms >= 0

    # 3. Invoke denied
    inv_denied = SimpleNamespace(
        tool="add_numbers",
        args={"a": 1, "b": 1},
        role="denied_role",
        workspace_dir=str(tmp_path),
        task_id="task-1",
    )
    res_denied = executor.invoke(inv_denied, allowed_files=[])  # type: ignore[arg-type]
    assert res_denied.status == "denied"
    assert res_denied.exit_code == 1

    # 4. wrap_for_langchain
    wrapped = executor.wrap_for_langchain(role="worker", task_id="task-1", allowed_files=[])
    assert len(wrapped) == 1
    assert isinstance(wrapped[0], BaseTool)
    assert wrapped[0].name == "add_numbers"

    # Run the wrapped tool
    out = wrapped[0].invoke({"a": 4, "b": 6})
    assert "10" in str(out)
