# FILE: src/asf/cli/commands/mcp.py
# ROLE: Implements `factory mcp list|test` (reports negotiated protocol version).
# ARCH REF: M1; p12; D-18
# OWNS: Argument parsing and output for this command group
# DOES NOT OWN: Business logic (lives in the imported modules)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/tools/mcp_client.py: McpManager (MCP)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: EXIT_OK, EXIT_USER, guard, project_root, renderer_for (shared CLI plumbing)
#   - called by src/asf/cli/app.py: register
#   - called by tests/cli/commands/test_mcp.py: mcp_list, mcp_test, register
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Never run agents or keep execution state in the CLI; write commands to the command table (IF-05) and read state/events (M1 is a thin client).
#   6. Support --output rich|plain|json through Renderer; prompts only when stdin and stdout are TTYs, otherwise exit 2 naming the missing flags (D-13).
#   7. Exit codes: 0 success, 1 user/validation error, 2 environment problem.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/cli/commands/test_mcp.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/commands/mcp.py` and `uv run mypy src/asf/cli/commands/mcp.py` are clean.

import typer

from asf.cli.context import EXIT_OK, EXIT_USER, guard, project_root, renderer_for
from asf.m5_shared.tools.mcp_client import McpManager


def mcp_list(output: str = "rich") -> int:
    """The MCP servers declared in mcp.toml (default-deny: nothing else is ever connected)."""
    manager = McpManager(project_root())
    names = manager.list_servers()
    renderer_for(output).table("MCP servers", ["name"], [[n] for n in names])
    return EXIT_OK


def mcp_test(name: str) -> int:
    manager = McpManager(project_root())
    renderer = renderer_for("plain")
    if name not in manager.list_servers():
        renderer.message(f"'{name}' is not declared in mcp.toml. `factory mcp list` shows the declared servers.", "error")
        return EXIT_USER
    report = manager.test_server(name)
    renderer.record(
        f"MCP server {name}",
        {"reachable": report.reachable, "protocol version": report.protocol_version or "-", "tools": ", ".join(report.tools) or "-", "problem": report.problem or "-"},
    )
    return EXIT_OK if report.reachable else EXIT_USER


def register(app: typer.Typer) -> None:
    """Attach the `mcp` command(s) to the root Typer app."""
    group = typer.Typer(help="List and test MCP servers.", no_args_is_help=True)

    @group.command("list")
    def list_cmd(output: str = typer.Option("rich", "--output", "-o")) -> None:
        raise typer.Exit(code=guard(lambda: mcp_list(output)))

    @group.command("test")
    def test_cmd(name: str) -> None:
        raise typer.Exit(code=guard(lambda: mcp_test(name)))

    app.add_typer(group, name="mcp")
