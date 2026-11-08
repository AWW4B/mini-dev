# FILE: src/asf/m5_shared/tools/mcp_client.py
# ROLE: Connects to MCP servers declared in mcp.toml (default-deny), lists tools and reports the negotiated protocol version.
# ARCH REF: M5; p12; D-18
# OWNS: MCP server lifecycle and tool loading
# DOES NOT OWN: Policy decisions (policy.py); execution (executor.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/tools/registry.py: ToolRegistry (register MCP tools)
#   - imports from src/asf/config/loader.py: load_layered (mcp.toml)
#   - called by src/asf/cli/commands/mcp.py: McpManager
#   - called by tests/m5_shared/tools/test_mcp_client.py: McpServerReport, McpManager
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Use langchain-mcp-adapters MultiServerMCPClient; stdio commands are argument lists from mcp.toml.
#   9. Servers are disabled until enabled in mcp.toml and each tool needs a policy entry.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/tools/test_mcp_client.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/tools/mcp_client.py` and `uv run mypy src/asf/m5_shared/tools/mcp_client.py` are clean.

from pydantic import BaseModel

from asf.m5_shared.tools.registry import ToolRegistry


class McpServerReport(BaseModel):
    name: str
    reachable: bool
    protocol_version: str | None
    tools: list[str]
    problem: str | None = None


class McpManager:
    def list_servers(self) -> list[str]:
        raise NotImplementedError

    def test_server(self, name: str) -> McpServerReport:
        raise NotImplementedError

    def load_tools(self, registry: ToolRegistry) -> int:
        raise NotImplementedError
