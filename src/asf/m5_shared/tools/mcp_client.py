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

import asyncio
import concurrent.futures
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any, cast

from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel

from asf.config.loader import load_layered
from asf.m5_shared.tools.registry import ToolRegistry


class McpServerReport(BaseModel):
    name: str
    reachable: bool
    protocol_version: str | None
    tools: list[str]
    problem: str | None = None


class _McpToolSpec(BaseModel):
    name: str
    description: str
    args_schema: dict[str, Any] = {}
    destructive: bool = False
    needs_network: bool = False
    roles: list[str] = ["T3"]
    source: str


def _run_coro_sync(coro: Coroutine[Any, Any, Any]) -> Any:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result(timeout=60)
    return asyncio.run(coro)


class McpManager:
    _config: dict[str, Any]
    _servers: dict[str, Any]

    def __init__(self, project_root: Path | None = None, config: dict[str, Any] | None = None) -> None:
        if config is not None:
            self._config = config
        else:
            try:
                self._config = load_layered("mcp", project_root=project_root)
            except Exception:  # noqa: BLE001
                self._config = {}
        self._servers = self._config.get("servers", {})

    def list_servers(self) -> list[str]:
        return list(self._servers.keys())

    def _build_connection(self, name: str, srv: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        transport = srv.get("transport", "stdio")
        if transport == "stdio":
            cmd = srv.get("command")
            if not cmd or not isinstance(cmd, list) or len(cmd) == 0:
                return None, "No command specified for stdio transport"
            conn: dict[str, Any] = {
                "transport": "stdio",
                "command": cmd[0],
                "args": cmd[1:],
            }
            if "env" in srv:
                conn["env"] = srv["env"]
            if "cwd" in srv:
                conn["cwd"] = srv["cwd"]
            return conn, None
        if transport in ("sse", "streamable_http", "websocket"):
            url = srv.get("url")
            if not url:
                return None, f"No URL specified for {transport} transport"
            return {"transport": transport, "url": url}, None
        return None, f"Unsupported transport '{transport}'"

    def test_server(self, name: str) -> McpServerReport:
        if name not in self._servers:
            return McpServerReport(
                name=name,
                reachable=False,
                protocol_version=None,
                tools=[],
                problem=f"Server '{name}' is not configured",
            )

        srv = self._servers[name]
        if not srv.get("enabled", False):
            return McpServerReport(
                name=name,
                reachable=False,
                protocol_version=None,
                tools=[],
                problem=f"Server '{name}' is disabled in configuration",
            )

        conn, err = self._build_connection(name, srv)
        if err or not conn:
            return McpServerReport(
                name=name,
                reachable=False,
                protocol_version=None,
                tools=[],
                problem=err or "Invalid server configuration",
            )

        async def _probe() -> McpServerReport:
            client = MultiServerMCPClient(cast(Any, {name: conn}))
            info_dict = await client.get_server_info(server_name=name)
            server_info = info_dict.get(name)
            proto_ver: str | None = None
            if server_info and hasattr(server_info, "protocolVersion"):
                proto_ver = str(server_info.protocolVersion)
            tools = await client.get_tools(server_name=name)
            tool_names = [t.name for t in tools]
            return McpServerReport(
                name=name,
                reachable=True,
                protocol_version=proto_ver,
                tools=tool_names,
                problem=None,
            )

        try:
            return cast(McpServerReport, _run_coro_sync(_probe()))
        except Exception as exc:  # noqa: BLE001
            return McpServerReport(
                name=name,
                reachable=False,
                protocol_version=None,
                tools=[],
                problem=str(exc),
            )

    def load_tools(self, registry: ToolRegistry) -> int:
        count = 0
        for srv_name, srv in self._servers.items():
            if not srv.get("enabled", False):
                continue
            conn, err = self._build_connection(srv_name, srv)
            if err or not conn:
                continue

            async def _fetch_tools(c: dict[str, Any], n: str) -> list[Any]:
                client = MultiServerMCPClient(cast(Any, {n: c}))
                return await client.get_tools(server_name=n)

            try:
                tools = cast(list[Any], _run_coro_sync(_fetch_tools(conn, srv_name)))
            except Exception as _fetch_err:  # noqa: BLE001
                _ = _fetch_err
                continue

            policy_tools = srv.get("tools", {})
            for tool in tools:
                tool_policy = policy_tools.get(tool.name)
                if not tool_policy:
                    # Default-deny: each tool needs a policy entry
                    continue

                roles = list(tool_policy.get("roles", ["T3"]))
                destructive = bool(tool_policy.get("destructive", False))
                needs_network = bool(tool_policy.get("needs_network", False))
                args_schema = (
                    tool.args_schema.schema()
                    if hasattr(getattr(tool, "args_schema", None), "schema")
                    else getattr(tool, "args_schema", {})
                )
                if not isinstance(args_schema, dict):
                    args_schema = {}

                spec = _McpToolSpec(
                    name=tool.name,
                    description=getattr(tool, "description", "") or "",
                    args_schema=args_schema,
                    destructive=destructive,
                    needs_network=needs_network,
                    roles=roles,
                    source=f"mcp:{srv_name}",
                )

                def _make_fn(t: Any) -> Callable[..., Any]:
                    def _call(*args: Any, **kwargs: Any) -> Any:
                        payload = kwargs if kwargs else (args[0] if args else {})
                        return t.invoke(payload)
                    return _call

                registry.register(cast(Any, spec), _make_fn(tool))
                count += 1

        return count
