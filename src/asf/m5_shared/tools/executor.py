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
#   - imports from src/asf/contracts/decisions.py: DecisionRequest (TOOL_PERMISSION requests)
#   - called by src/asf/m5_shared/tools/codeexec/runner.py: ToolExecutor
#   - called by src/asf/m4_execution/worker/strategies.py: ToolExecutor
#   - called by tests/m5_shared/tools/test_executor.py: ToolExecutor
#   - called by src/asf/m4_execution/worker/worker_graph.py: ToolExecutor
#   - called by src/asf/m3_orchestration/run_graph.py: ToolExecutor
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

import inspect
import logging
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from langchain_core.tools import BaseTool

from asf.contracts.decisions import DecisionRequest
from asf.contracts.errors import ApprovalRequired, PolicyDenied, SandboxUnavailable  # noqa: F401
from asf.contracts.tools import SandboxTier, ToolInvocation, ToolResult
from asf.m5_shared.decisions.broker import DecisionBroker
from asf.m5_shared.events.redaction import redact_text
from asf.m5_shared.metrics.collector import MetricsCollector
from asf.m5_shared.tools.policy import PolicyEngine, Verdict
from asf.m5_shared.tools.registry import ToolRegistry
from asf.platform.select import get_platform

logger = logging.getLogger(__name__)


class _DelegatingTool(BaseTool):
    name: str
    description: str
    _executor: "ToolExecutor"
    _role: str
    _task_id: str | None
    _allowed_files: list[str]

    def __init__(
        self,
        name: str,
        description: str,
        executor: "ToolExecutor",
        role: str,
        task_id: str | None,
        allowed_files: list[str],
    ) -> None:
        super().__init__(name=name, description=description)
        self._executor = executor
        self._role = role
        self._task_id = task_id
        self._allowed_files = allowed_files

    def _run(self, **kwargs: Any) -> Any:
        inv = ToolInvocation(
            tool=self.name,
            args=kwargs,
            role=self._role,
            task_id=self._task_id,  # type: ignore[arg-type]
            workspace_dir=".",
        )
        res = self._executor.invoke(inv, self._allowed_files)
        return res.output


class ToolExecutor:
    registry: ToolRegistry
    policy: PolicyEngine
    broker: DecisionBroker | None
    collector: MetricsCollector | None
    tier: SandboxTier | None

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        policy: PolicyEngine | None = None,
        broker: DecisionBroker | None = None,
        collector: MetricsCollector | None = None,
        tier: SandboxTier | None = None,
    ) -> None:
        self.registry = registry or ToolRegistry()
        self.policy = policy or PolicyEngine()
        self.broker = broker
        self.collector = collector
        self.tier = tier

    def active_tier(self) -> SandboxTier:
        if self.tier is not None:
            return self.tier
        return get_platform().sandbox().tier

    def invoke(self, invocation: ToolInvocation, allowed_files: list[str]) -> ToolResult:
        t0 = time.monotonic()
        active_tier = self.active_tier()

        try:
            spec, fn = self.registry.get(invocation.tool)
        except Exception:
            return ToolResult(
                tool=invocation.tool,
                status="error",
                exit_code=1,
                output=f"Tool '{invocation.tool}' not found",
                duration_ms=0,
                sandbox_tier=active_tier,
            )

        verdict_obj = self.policy.check(invocation, spec, active_tier, allowed_files)
        verdict_str = (
            verdict_obj.verdict.value
            if hasattr(verdict_obj.verdict, "value")
            else str(verdict_obj.verdict)
        )

        if verdict_str == Verdict.DENY.value:
            duration = int((time.monotonic() - t0) * 1000)
            return ToolResult(
                tool=invocation.tool,
                status="denied",
                exit_code=1,
                output=verdict_obj.reason,
                duration_ms=duration,
                sandbox_tier=active_tier,
            )

        if verdict_str == Verdict.NEEDS_APPROVAL.value:
            # The tool is NOT run: the user is asked through the DecisionBroker (TOOL_PERMISSION is never auto-approved)
            # and the agent gets a denial it can react to; it may call the tool again once the decision is granted.
            duration = int((time.monotonic() - t0) * 1000)
            if self.broker is None:
                output = f"Approval required but no DecisionBroker available: {verdict_obj.reason}"
            else:
                decision_id = f"dec-tool-{invocation.task_id or 'adhoc'}-{invocation.tool}"
                self.broker.request(
                    DecisionRequest.model_validate(
                        {
                            "decision_id": decision_id,
                            "run_id": str(invocation.task_id or "adhoc"),
                            "task_id": invocation.task_id,
                            "kind": "tool_permission",
                            "requester": "asf.m5_shared.tools.executor",
                            "question": f"Allow the agent to run '{invocation.tool}'? {verdict_obj.reason}",
                            "options": ["allow_once", "deny"],
                            "default_on_timeout": "deny",
                        }
                    )
                )
                output = f"Approval requested ({decision_id}); the tool was not run: {verdict_obj.reason}"
            return ToolResult(
                tool=invocation.tool,
                status="denied",
                exit_code=1,
                output=output,
                duration_ms=duration,
                sandbox_tier=active_tier,
            )

        try:
            call_args = dict(invocation.args)
            if "root" in inspect.signature(fn).parameters:
                call_args["root"] = Path(invocation.workspace_dir)  # the workspace is chosen by the platform, never by the agent
            raw_res = fn(**call_args)
            status = "ok"
            exit_code = 0
        except Exception as err:  # noqa: BLE001 - any tool failure becomes an error result for the agent
            logger.info("tool %s failed: %s", invocation.tool, err)
            raw_res = str(err)
            status = "error"
            exit_code = 1

        duration_ms = int((time.monotonic() - t0) * 1000)

        # Sanitise, strip control characters, redact, truncate
        text = str(raw_res)
        sanitized = "".join(ch for ch in text if ch in "\n\t\r" or ord(ch) >= 32)
        truncated = sanitized[:50000]
        output = redact_text(truncated)

        if self.collector is not None:
            tool_metric = SimpleNamespace(
                run_id="run-local",
                task_id=invocation.task_id,
                tool=invocation.tool,
                duration_ms=duration_ms,
                exit_status=status,
            )
            try:
                self.collector.record_tool(tool_metric)  # type: ignore[arg-type]
            except Exception:  # noqa: BLE001 - metrics must never fail a tool call, but a lost record is logged
                logger.warning("could not record the metric for tool %s", invocation.tool, exc_info=True)

        return ToolResult(
            tool=invocation.tool,
            status=status,
            exit_code=exit_code,
            output=output,
            duration_ms=duration_ms,
            sandbox_tier=active_tier,
        )

    def wrap_for_langchain(self, role: str, task_id: str | None, allowed_files: list[str]) -> list[BaseTool]:
        specs = self.registry.specs_for(role)
        tools: list[BaseTool] = []

        for spec in specs:
            tool = _DelegatingTool(
                name=spec.name,
                description=spec.description,
                executor=self,
                role=role,
                task_id=task_id,
                allowed_files=allowed_files,
            )
            tools.append(tool)

        return tools
