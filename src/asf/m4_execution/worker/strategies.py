# FILE: src/asf/m4_execution/worker/strategies.py
# ROLE: Worker strategies: tool_loop, whole_file_edit, diff_edit, code_exec — all producing the same metrics.
# ARCH REF: M4; p07; D-09 worker strategies; D-19
# OWNS: Strategy step functions
# DOES NOT OWN: Gates (verification)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (IF-12 model calls)
#   - imports from src/asf/m5_shared/tools/executor.py: ToolExecutor (IF-14 tool calls)
#   - imports from src/asf/m5_shared/tools/codeexec/runner.py: execute_code (code_exec strategy)
#   - imports from src/asf/contracts/tasks.py: LeafTaskSpec (task)
#   - imports from src/asf/contracts/tools.py: ToolInvocation (tool calls through the executor)
#   - imports from src/asf/platform/select.py: get_platform (git apply)
#   - called by src/asf/m4_execution/worker/worker_graph.py: run_strategy, WorkerStrategyName
#   - called by tests/m4_execution/worker/test_strategies.py: run_strategy, WorkerStrategyName, WorkerBlocked, WorkerFormatError
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. code_exec is used only when the active sandbox tier is A; otherwise fall back to tool_loop and log why.
#   6. Use these Agent Skills (load via SkillsRegistry): skills/python-module-from-contract/SKILL.md.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m4_execution/worker/test_strategies.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m4_execution/worker/strategies.py` and `uv run mypy src/asf/m4_execution/worker/strategies.py` are clean.

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Literal, cast

from asf.contracts.tasks import LeafTaskSpec
from asf.contracts.tools import ToolInvocation
from asf.m5_shared.gateway.gateway import ModelGateway
from asf.m5_shared.tools.codeexec.runner import execute_code
from asf.m5_shared.tools.executor import ToolExecutor
from asf.platform.select import get_platform

logger = logging.getLogger(__name__)

WorkerStrategyName = Literal["tool_loop", "whole_file_edit", "diff_edit", "code_exec"]

FORMAT_REPAIRS_PER_STEP = 2
_TOOL_OUTPUT_CHARS = 4000
_ROLE = "T2"

_SYSTEM = (
    "You are a coding worker. Work only on the files listed under ALLOWED FILES; writes anywhere else are denied. "
    "Reply with ONE JSON object and nothing else.\n"
    "{shape}\n"
    "Use done when the task is complete, blocked when you cannot proceed (missing context or a gap in the contract)."
)
_TOOL_SHAPE = (
    'Shapes: {"action": "tool", "tool": "<name>", "args": {...}} | {"action": "done", "message": "<self-report>"} | '
    '{"action": "blocked", "message": "<reason>"}. Tools: read_file(rel_path), write_file(rel_path, content), search_code(pattern), '
    "run_tests(selectors: list of test ids), run_linter(files: list of paths)."
)
_FILES_SHAPE = (
    'Shape: {"action": "done", "message": "<self-report>", "files": {"<allowed path>": "<complete new file content>"}} '
    'or {"action": "blocked", "message": "<reason>"}.'
)
_DIFF_SHAPE = (
    'Shape: {"action": "done", "message": "<self-report>", "diff": "<unified diff, a/ b/ prefixes>"} '
    'or {"action": "blocked", "message": "<reason>"}.'
)
_SCRIPT_SHAPE = (
    'Shape: {"action": "done", "message": "<self-report>", "script": "<python script using the tool facade>"} '
    'or {"action": "blocked", "message": "<reason>"}.'
)


class WorkerBlocked(Exception):
    """The worker cannot proceed (missing context or a contract gap); the orchestrator must re-plan."""


class WorkerFormatError(Exception):
    """The model kept answering outside the required JSON shape."""


def _extract_json(text: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object found in the reply")
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict) or "action" not in parsed:
        raise ValueError("the reply must be a JSON object with an 'action' field")
    return cast(dict[str, Any], parsed)


def _model_text(gateway: ModelGateway, prompt: str) -> str:
    reply = gateway.model_for(cast(Any, _ROLE), purpose="code_step").invoke(prompt)
    return str(getattr(reply, "content", reply))


def _ask(gateway: ModelGateway, prompt: str) -> dict[str, Any]:
    """One model step with up to FORMAT_REPAIRS_PER_STEP re-asks when the answer is not the required JSON."""
    current = prompt
    last_error = ""
    for _ in range(FORMAT_REPAIRS_PER_STEP + 1):
        text = _model_text(gateway, current)
        try:
            return _extract_json(text)
        except ValueError as err:
            last_error = str(err)
            current = f"{prompt}\n\nYour previous reply was rejected: {last_error}. Reply with exactly one JSON object."
    raise WorkerFormatError(f"the model did not produce a valid step after {FORMAT_REPAIRS_PER_STEP + 1} tries: {last_error}")


def _header(spec: LeafTaskSpec, context: str, shape: str) -> str:
    capsules = "\n".join(f"- {c.module_id}.{c.operation}: " + " ".join(c.lines) for c in spec.capsules)
    return (
        _SYSTEM.format(shape=shape)
        + f"\n\nTASK: {spec.goal}\nALLOWED FILES: {', '.join(spec.allowed_files)}\n"
        + f"READ-ONLY FILES: {', '.join(spec.read_only_files) or '(none)'}\n"
        + f"ACCEPTANCE TESTS: {', '.join(spec.acceptance_test_refs)}\nDEPENDENCY CONTRACTS:\n{capsules or '(none)'}\n\n{context}"
    )


def _blocked(step: dict[str, Any]) -> WorkerBlocked:
    return WorkerBlocked(str(step.get("message", "blocked")))


def _deadline(spec: LeafTaskSpec) -> float:
    return time.monotonic() + spec.step_budget.wall_clock_s


def _invoke_tool(executor: ToolExecutor, spec: LeafTaskSpec, tool: str, args: dict[str, Any], worktree: str) -> str:
    invocation = ToolInvocation.model_validate(
        {"tool": tool, "args": args, "role": _ROLE, "task_id": str(spec.task_id), "workspace_dir": worktree}
    )
    result = executor.invoke(invocation, spec.allowed_files)
    return f"[{result.status}] {result.output[:_TOOL_OUTPUT_CHARS]}"


def _tool_loop(spec: LeafTaskSpec, worktree: str, gateway: ModelGateway, executor: ToolExecutor, context: str) -> str:
    transcript = _header(spec, context, _TOOL_SHAPE)
    deadline = _deadline(spec)
    for turn in range(1, spec.step_budget.max_turns + 1):
        if time.monotonic() > deadline:
            raise WorkerBlocked("SPEC_TOO_LARGE: the wall-clock budget for the attempt was exhausted")
        step = _ask(gateway, transcript)
        action = step.get("action")
        if action == "done":
            return f"tool_loop finished in {turn} step(s): {step.get('message', '')}"
        if action == "blocked":
            raise _blocked(step)
        if action != "tool" or not isinstance(step.get("tool"), str):
            transcript += f"\n\nTurn {turn}: invalid action {action!r}; use tool, done or blocked."
            continue
        args = step.get("args") if isinstance(step.get("args"), dict) else {}
        observation = _invoke_tool(executor, spec, str(step["tool"]), cast(dict[str, Any], args), worktree)
        transcript += f"\n\nTurn {turn}: {step['tool']}({json.dumps(args)[:500]})\nResult: {observation}"
    raise WorkerBlocked("SPEC_TOO_LARGE: the step budget was exhausted before the model reported done")


def _whole_file_edit(spec: LeafTaskSpec, worktree: str, gateway: ModelGateway, executor: ToolExecutor, context: str) -> str:
    step = _ask(gateway, _header(spec, context, _FILES_SHAPE))
    if step.get("action") == "blocked":
        raise _blocked(step)
    files = step.get("files")
    if not isinstance(files, dict) or not files:
        raise WorkerFormatError("whole_file_edit needs a non-empty 'files' object")
    for path, content in files.items():
        outcome = _invoke_tool(executor, spec, "write_file", {"rel_path": str(path), "content": str(content)}, worktree)
        if not outcome.startswith("[ok]"):
            raise WorkerFormatError(f"writing {path} failed: {outcome}")
    return f"whole_file_edit wrote {len(files)} file(s): {step.get('message', '')}"


_DIFF_PATH = re.compile(r"^\+\+\+ b/(.+?)\s*$", re.MULTILINE)


def _apply_unified_diff(diff: str, allowed: list[str], worktree: str) -> list[str]:
    paths = [p.strip() for p in _DIFF_PATH.findall(diff)]
    allowed_set = {Path(a).as_posix() for a in allowed}
    outside = [p for p in paths if Path(p).as_posix() not in allowed_set]
    if not paths or outside:
        raise WorkerFormatError(f"the diff touches files outside the allowed set: {outside or 'no files found'}")
    patch = Path(worktree) / ".asf_worker.patch"
    patch.write_text(diff if diff.endswith("\n") else diff + "\n", encoding="utf-8")
    try:
        result = get_platform().run_process(["git", "apply", "--whitespace=nowarn", patch.name], cwd=Path(worktree), timeout_s=60)
    finally:
        patch.unlink(missing_ok=True)
    if result.exit_code != 0:
        raise WorkerFormatError("the diff does not apply: " + result.stderr.decode("utf-8", errors="replace")[:500])
    return paths


def _diff_edit(spec: LeafTaskSpec, worktree: str, gateway: ModelGateway, executor: ToolExecutor, context: str) -> str:
    _ = executor
    step = _ask(gateway, _header(spec, context, _DIFF_SHAPE))
    if step.get("action") == "blocked":
        raise _blocked(step)
    diff = step.get("diff")
    if not isinstance(diff, str) or not diff.strip():
        raise WorkerFormatError("diff_edit needs a non-empty 'diff' string")
    paths = _apply_unified_diff(diff, spec.allowed_files, worktree)
    return f"diff_edit patched {len(paths)} file(s): {step.get('message', '')}"


def _code_exec(spec: LeafTaskSpec, worktree: str, gateway: ModelGateway, executor: ToolExecutor, context: str) -> str:
    _ = worktree
    step = _ask(gateway, _header(spec, context, _SCRIPT_SHAPE))
    if step.get("action") == "blocked":
        raise _blocked(step)
    script = step.get("script")
    if not isinstance(script, str) or not script.strip():
        raise WorkerFormatError("code_exec needs a non-empty 'script' string")
    result = execute_code(executor, script, _ROLE, str(spec.task_id), spec.allowed_files)
    return f"code_exec finished: {step.get('message', '')} ({str(getattr(result, 'status', 'ok'))})"


_STRATEGIES = {
    "tool_loop": _tool_loop,
    "whole_file_edit": _whole_file_edit,
    "diff_edit": _diff_edit,
    "code_exec": _code_exec,
}


def run_strategy(
    name: WorkerStrategyName,
    spec: LeafTaskSpec,
    worktree: str,
    *,
    gateway: ModelGateway,
    executor: ToolExecutor,
    context: str = "",
) -> str:
    """Run the bounded loop; return the worker self-report.

    code_exec is only used when the active sandbox tier is A; otherwise it falls back to tool_loop (and says why).
    """
    chosen: str = name
    if chosen == "code_exec" and str(executor.active_tier()) != "A":
        logger.warning("code_exec needs sandbox tier A (active: %s); falling back to tool_loop", executor.active_tier())
        chosen = "tool_loop"
    if chosen not in _STRATEGIES:
        raise ValueError(f"unknown worker strategy '{name}'")
    return _STRATEGIES[chosen](spec, worktree, gateway, executor, context)
