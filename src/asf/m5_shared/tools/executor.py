# FILE: src/asf/m5_shared/tools/executor.py
# ROLE: The single choke point for every tool call (builtin, MCP, code_exec): policy, sandbox, timeout, sanitising, events and metrics.
# ARCH REF: M5; p12 Tool Executor; IF-14 ToolInvocation; D-16; D-19; D-14b narrative events
# OWNS: Executing tool calls and emitting TOOL_CALLED / TOOL_RESULT
# DOES NOT OWN: Tool definitions (registry, builtin_tools, mcp_client)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tools.py: ToolInvocation, ToolResult, SandboxTier (IF-14)
#   - imports from src/asf/m5_shared/tools/registry.py: ToolRegistry (lookup)
#   - imports from src/asf/m5_shared/tools/policy.py: PolicyEngine, Verdict (decisions)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (approvals)
#   - imports from src/asf/m5_shared/metrics/collector.py: MetricsCollector (ToolMetric)
#   - imports from src/asf/m5_shared/events/redaction.py: redact_text (redaction)
#   - imports from src/asf/platform/select.py: get_platform (platform adapter)
#   - imports from src/asf/contracts/errors.py: PolicyDenied, ApprovalRequired, SandboxUnavailable (error types)
#   - called by src/asf/m5_shared/tools/codeexec/runner.py: ToolExecutor
#   - called by src/asf/m4_execution/worker/strategies.py: ToolExecutor
#   - called by tests/m5_shared/tools/test_executor.py: ToolExecutor
#   - emits/consumes: emits TOOL_CALLED (tool, args_summary, reason, approved|denied|pending_approval, sandbox_tier, via_code_exec) and TOOL_RESULT (summary, exit_status, duration, output_ref) for EVERY call, including calls from code_exec scripts
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Graphs never receive raw tools: wrap_for_langchain returns StructuredTools whose function calls invoke().
#   9. Treat tool output as untrusted: truncate, strip control characters, redact, tag provenance.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/tools/test_executor.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/tools/executor.py` and `uv run mypy src/asf/m5_shared/tools/executor.py` are clean.

from langchain_core.tools import BaseTool

from asf.contracts.tools import SandboxTier, ToolInvocation, ToolResult


class ToolExecutor:
    def invoke(self, invocation: ToolInvocation, allowed_files: list[str]) -> ToolResult:
        raise NotImplementedError

    def wrap_for_langchain(self, role: str, task_id: str | None, allowed_files: list[str]) -> list[BaseTool]:
        raise NotImplementedError

    def active_tier(self) -> SandboxTier:
        raise NotImplementedError
