# FILE: src/asf/contracts/tools.py
# ROLE: Defines tool specs, ToolInvocation/ToolResult (IF-14), skill manifests (IF-23) and sandbox tiers.
# ARCH REF: p12; IF-14; IF-23; D-16; D-17; D-19; D-21
# OWNS: Tool and skill shapes
# DOES NOT OWN: Enforcement (src/asf/m5_shared/tools/executor.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/ids.py: TaskId (typed ids)
#   - called by src/asf/m5_shared/tools/registry.py: ToolSpec
#   - called by src/asf/m5_shared/tools/policy.py: ToolInvocation, ToolSpec, SandboxTier
#   - called by src/asf/m5_shared/tools/executor.py: ToolInvocation, ToolResult, SandboxTier
#   - called by src/asf/m5_shared/tools/skills.py: SkillManifest
#   - called by src/asf/m5_shared/tools/codeexec/facade_gen.py: ToolSpec
#   - called by src/asf/platform/base.py: SandboxTier
#   - called by src/asf/platform/fallback.py: SandboxTier
#   - called by tests/contracts/test_tools.py: SandboxTier, ToolSpec, ToolInvocation, ToolResult, SkillManifest
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. This file is declarations only: Pydantic models, enums and type aliases. Add field validators only where the docstring of a field states a constraint.
#   6. Every model must round-trip through model_dump_json() / model_validate_json() unchanged; the JSON Schema exported from these models is the published contract (D-39: no hand-written JSON).
#   7. Changing a field name or type is a contract change: stop and report instead.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; business logic; I/O; imports from asf.m1-m5 packages, asf.cli, asf.web or asf.platform
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/contracts/test_tools.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/contracts/tools.py` and `uv run mypy src/asf/contracts/tools.py` are clean.

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from asf.contracts.ids import TaskId


class SandboxTier(StrEnum):
    A = "A"   # real sandbox: filesystem + network isolation
    B = "B"   # contained: process tree, limits, timeouts; approval per run
    C = "C"   # none usable: static checks only


class ToolSpec(BaseModel):
    name: str
    description: str
    args_schema: dict[str, Any]
    destructive: bool = False
    needs_network: bool = False
    roles: list[str]
    source: str = Field(description="builtin | mcp:<server> | codeexec")


class ToolInvocation(BaseModel):
    """IF-14 request."""
    tool: str
    args: dict[str, Any]
    role: str
    task_id: TaskId | None = None
    workspace_dir: str = Field(description="absolute path as text, produced by pathlib on this machine")
    reason: str | None = Field(default=None, description="optional explanation supplied by the agent (D-14b)")
    via_code_exec: bool = False


class ToolResult(BaseModel):
    """IF-14 response."""
    tool: str
    status: str = Field(description="ok | error | denied | timeout")
    exit_code: int | None = None
    output: str = Field(description="sanitised and truncated; untrusted")
    output_ref: str | None = None
    duration_ms: int
    sandbox_tier: SandboxTier | None = None


class SkillManifest(BaseModel):
    """IF-23: metadata only (progressive disclosure)."""
    name: str
    description: str
    version: str
    allowed_tools: list[str] = Field(default_factory=list)
    path: str
    body_chars: int
