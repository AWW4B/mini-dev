# FILE: src/asf/m5_shared/tools/registry.py
# ROLE: Holds every tool spec and callable (builtin, MCP, codeexec) — the single source for the executor and the code-mode facade.
# ARCH REF: M5; p12 Tools Registry; D-16; D-19 one source of truth
# OWNS: Tool registration and lookup
# DOES NOT OWN: Permission checks (policy.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tools.py: ToolSpec (spec)
#   - called by src/asf/m5_shared/tools/executor.py: ToolRegistry
#   - called by src/asf/m5_shared/tools/builtin_tools.py: ToolRegistry
#   - called by src/asf/m5_shared/tools/mcp_client.py: ToolRegistry
#   - called by src/asf/m5_shared/tools/codeexec/search.py: ToolRegistry
#   - called by tests/m5_shared/tools/test_registry.py: ToolRegistry
#   - called by tests/m5_shared/tools/test_executor.py: ToolRegistry
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/tools/test_registry.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/tools/registry.py` and `uv run mypy src/asf/m5_shared/tools/registry.py` are clean.

from collections.abc import Callable
from typing import Any

from asf.contracts.tools import ToolSpec


class ToolRegistry:
    _tools: dict[str, tuple[ToolSpec, Callable[..., Any]]]

    def __init__(self) -> None:
        self._tools = {}

    def register(self, spec: ToolSpec, fn: Callable[..., Any]) -> None:
        self._tools[spec.name] = (spec, fn)

    def get(self, name: str) -> tuple[ToolSpec, Callable[..., Any]]:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry")
        return self._tools[name]

    def specs_for(self, role: str) -> list[ToolSpec]:
        return [
            spec
            for spec, _ in self._tools.values()
            if role in spec.roles or "*" in spec.roles
        ]
