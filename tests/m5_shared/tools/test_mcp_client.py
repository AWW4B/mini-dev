# FILE: tests/m5_shared/tools/test_mcp_client.py
# ROLE: Tests that prove src/asf/m5_shared/tools/mcp_client.py meets its DONE WHEN conditions.
# ARCH REF: M5; p12; D-18; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/tools/mcp_client.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/tools/mcp_client.py: McpServerReport, McpManager (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/tools/test_mcp_client.py` on Windows and Linux once src/asf/m5_shared/tools/mcp_client.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/tools/test_mcp_client.py` and `uv run mypy tests/m5_shared/tools/test_mcp_client.py` are clean.

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from asf.m5_shared.tools.mcp_client import McpManager, McpServerReport


def test_mcp_server_report_meets_contract() -> None:
    """Prove McpServerReport behaves as declared in src/asf/m5_shared/tools/mcp_client.py."""
    report = McpServerReport(
        name="server1",
        reachable=True,
        protocol_version="2024-11-05",
        tools=["search", "fetch"],
    )
    assert report.name == "server1"
    assert report.reachable is True
    assert report.protocol_version == "2024-11-05"
    assert report.tools == ["search", "fetch"]
    assert report.problem is None

    err = McpServerReport(
        name="server2",
        reachable=False,
        protocol_version=None,
        tools=[],
        problem="Connection refused",
    )
    assert err.reachable is False
    assert err.problem == "Connection refused"


def test_mcp_manager_meets_contract(fake_paths: Any) -> None:
    """Prove McpManager behaves as declared in src/asf/m5_shared/tools/mcp_client.py."""
    _ = fake_paths
    test_config = {
        "servers": {
            "disabled_server": {
                "enabled": False,
                "transport": "stdio",
                "command": ["uvx", "fake-server"],
            },
            "mocked_server": {
                "enabled": True,
                "transport": "stdio",
                "command": ["python", "-m", "fake_server"],
                "tools": {
                    "allowed_tool": {
                        "roles": ["T3"],
                        "destructive": False,
                    }
                },
            },
        }
    }

    mgr = McpManager(config=test_config)

    # 1. list_servers
    servers = mgr.list_servers()
    assert "disabled_server" in servers
    assert "mocked_server" in servers

    # 2. test_server - disabled
    disabled_report = mgr.test_server("disabled_server")
    assert disabled_report.reachable is False
    assert "disabled" in (disabled_report.problem or "")

    # 3. test_server - unknown
    unknown_report = mgr.test_server("non_existent")
    assert unknown_report.reachable is False
    assert "not configured" in (unknown_report.problem or "")

    # 4. test_server - mocked success
    fake_info = SimpleNamespace(protocolVersion="2024-11-05")
    fake_tool_allowed = SimpleNamespace(
        name="allowed_tool",
        description="An allowed tool",
        args_schema={"type": "object"},
        invoke=lambda args: "result",
    )
    fake_tool_unconfigured = SimpleNamespace(
        name="unconfigured_tool",
        description="Not in policy",
        args_schema={"type": "object"},
        invoke=lambda args: "fail",
    )

    with (
        patch("asf.m5_shared.tools.mcp_client.MultiServerMCPClient.get_server_info", new_callable=AsyncMock) as mock_info,
        patch("asf.m5_shared.tools.mcp_client.MultiServerMCPClient.get_tools", new_callable=AsyncMock) as mock_tools,
    ):
        mock_info.return_value = {"mocked_server": fake_info}
        mock_tools.return_value = [fake_tool_allowed, fake_tool_unconfigured]

        report = mgr.test_server("mocked_server")
        assert report.reachable is True
        assert report.protocol_version == "2024-11-05"
        assert "allowed_tool" in report.tools
        assert "unconfigured_tool" in report.tools

        # 5. load_tools - only tools with policy entry get registered
        class FakeRegistry:
            def __init__(self) -> None:
                self.tools: dict[str, tuple[Any, Any]] = {}

            def register(self, spec: Any, fn: Any) -> None:
                self.tools[spec.name] = (spec, fn)

        registry = FakeRegistry()
        count = mgr.load_tools(registry)  # type: ignore[arg-type]
        assert count == 1
        assert "allowed_tool" in registry.tools
        assert "unconfigured_tool" not in registry.tools
        spec, _ = registry.tools["allowed_tool"]
        assert spec.source == "mcp:mocked_server"
        assert spec.roles == ["T3"]
