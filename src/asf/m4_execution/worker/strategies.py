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
#   - imports from src/asf/m5_shared/memory/device_budget.py: load_memory_config (tool output percentages)
#   - imports from src/asf/m5_shared/memory/tool_outputs.py: ShapedOutput, ToolOutputPolicy (shaped tool results)
#   - imports from src/asf/m5_shared/context/compaction.py: compact_history (older turns)
#   - called by src/asf/m4_execution/worker/worker_graph.py: run_strategy, WorkerStrategyName
#   - called by tests/m4_execution/worker/test_strategies.py: run_strategy, WorkerStrategyName, WorkerBlocked, WorkerFormatError
#   - imports from src/asf/m5_shared/trace.py: trace_event (every worker turn and tool result)
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
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Literal, cast

from asf.contracts.tasks import LeafTaskSpec
from asf.contracts.tools import ToolInvocation
from asf.m5_shared.context.compaction import compact_history
from asf.m5_shared.gateway.gateway import ModelGateway
from asf.m5_shared.memory.device_budget import load_memory_config
from asf.m5_shared.memory.tool_outputs import ShapedOutput, ToolOutputPolicy
from asf.m5_shared.tools.codeexec.runner import execute_code
from asf.m5_shared.tools.executor import ToolExecutor
from asf.m5_shared.trace import trace_event
from asf.platform.select import get_platform

logger = logging.getLogger(__name__)

WorkerStrategyName = Literal["tool_loop", "whole_file_edit", "diff_edit", "code_exec"]

FORMAT_REPAIRS_PER_STEP = 2
_TOOL_OUTPUT_CHARS = 4000
_ROLE = "T2"  # the role tools are permitted for; the MODEL role may differ on a helper attempt (below)
_MODEL_ROLE: ContextVar[str] = ContextVar("asf_worker_model_role", default="T2")

_SYSTEM = (
    "You are a coding worker. Work only on the files listed under ALLOWED FILES; writes anywhere else are denied. "
    "Reply with ONE JSON object and nothing else.\n"
    "{shape}\n"
    "Use done when the task is complete, blocked only when you tried and cannot proceed (a real gap in the contract). "
    "The modules under DEPENDENCY CONTRACTS already exist: import them by those signatures and never write them again. Create every ALLOWED FILE that does not exist yet."
)
_TOOL_SHAPE = (
    'Shapes: {"action": "tool", "tool": "<name>", "args": {...}} | {"action": "done", "message": "<self-report>"} | '
    '{"action": "blocked", "message": "<reason>"}. Tools: read_file(rel_path), write_file(rel_path, content), search_code(pattern), '
    "run_tests(selectors: list of test FILE paths, for example [\"tests/test_core.py\"]; pass the ACCEPTANCE TESTS files), run_linter(files: list of paths)."
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


_WRITE_PATH = re.compile(r'"(?:rel_path|path)"\s*:\s*"([^"\n]+)"')
_WRITE_BODY = re.compile(r'"content"\s*:\s*"(.*)"\s*\}?\s*\}?\s*(?:```)?\s*$', re.DOTALL)
_UNESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "'": "'", "/": "/"}


def _salvage_write(text: str) -> dict[str, Any] | None:
    """A write_file reply whose content is not valid JSON, read anyway. The 7B coder puts raw double quotes (an f-string, a print)
    inside the JSON string: json.loads fails, the re-ask made it answer 'blocked: invalid escape' and the task escalated.
    The path and the content are unambiguous, so the content is unescaped by hand."""
    path, body = _WRITE_PATH.search(text), _WRITE_BODY.search(text)
    if path is None or body is None or '"write_file"' not in text:
        return None
    raw = re.sub(r"\\(.)", lambda m: _UNESCAPES.get(m.group(1), "\\" + m.group(1)), body.group(1))
    raw = re.sub(r'"\s*[}\]`]*\s*$', "", raw)  # the JSON's closing quote and braces are not part of the file (a real run wrote '"}' as the last line of cli.py)
    return {"action": "tool", "tool": "write_file", "args": {"rel_path": path.group(1), "content": raw}}


def _extract_json(text: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object found in the reply")
    try:
        parsed = json.loads(text[start : end + 1], strict=False)
    except json.JSONDecodeError as err:
        salvaged = _salvage_write(text[start : end + 1])
        if salvaged is None:
            raise ValueError(f"the reply is not valid JSON ({err.msg} at char {err.pos}): escape every double quote inside a string as \\\" and write line breaks as \\n") from err
        return salvaged
    if not isinstance(parsed, dict) or "action" not in parsed:
        raise ValueError("the reply must be a JSON object with an 'action' field")
    return cast(dict[str, Any], parsed)


_TOOL_NAMES = ("read_file", "write_file", "search_code", "run_tests", "run_linter")


def _repair_tool_step(step: dict[str, Any]) -> dict[str, Any]:
    """A 7B coder often answers {"action": "write_file", "rel_path": ..., "content": ...}: the tool name in the action field.

    That reply is unambiguous, so it is read as {"action": "tool", "tool": "write_file", "args": {...}} instead of costing a turn
    (every attempt in the first real run ended on the step budget this way).
    """
    action = step.get("action")
    if action in _TOOL_NAMES and not isinstance(step.get("tool"), str):
        args = step.get("args") if isinstance(step.get("args"), dict) else {k: v for k, v in step.items() if k not in ("action", "message", "tool")}
        return {"action": "tool", "tool": action, "args": args}
    return step


def _test_selectors(spec: LeafTaskSpec, args: dict[str, Any]) -> dict[str, Any]:
    """run_tests takes test file paths. The 7B coder passed test function names ("test_top_words_basic"): pytest answered exit 4 (file not
    found), the coder reported the tests missing and blocked the task. Anything that is not a path to a test file becomes the task's own."""
    given = args.get("selectors")
    paths = [str(x) for x in given] if isinstance(given, list) else []
    if paths and all(".py" in x for x in paths):
        return args
    return {**args, "selectors": list(spec.acceptance_test_refs)}


def _model_text(gateway: ModelGateway, prompt: str) -> str:
    reply = gateway.model_for(cast(Any, _MODEL_ROLE.get()), purpose="code_step").invoke(prompt)
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


def _tool_source(executor: ToolExecutor, tool: str) -> Any:
    try:
        return "mcp" if executor.registry.get(tool)[0].source == "mcp" else "builtin"
    except Exception:  # noqa: BLE001 - an unknown tool is rejected by the executor itself; shaping treats it as builtin
        return "builtin"


def _shaped_tool(policy: ToolOutputPolicy, executor: ToolExecutor, spec: LeafTaskSpec, tool: str, args: dict[str, Any], worktree: str) -> ShapedOutput:
    """Run a tool and shape its output for the transcript (memory.toml [tools]: % caps, head/tail, untrusted MCP marking)."""
    invocation = ToolInvocation.model_validate(
        {"tool": tool, "args": args, "role": _ROLE, "task_id": str(spec.task_id), "workspace_dir": worktree}
    )
    result = executor.invoke(invocation, spec.allowed_files)
    shaped = policy.shape(tool, str(result.output), status=str(result.status), source=_tool_source(executor, tool))
    return shaped.model_copy(update={"text": f"[{result.status}] {shaped.text}"})


def _policy(spec: LeafTaskSpec) -> ToolOutputPolicy:
    return ToolOutputPolicy(load_memory_config(), window_tokens=spec.context_budget_tokens)


_ACCEPTANCE_CHARS = 6000
MAX_BLOCK_REFUSALS = 2


def _acceptance_source(spec: LeafTaskSpec, worktree: str) -> str:
    """The acceptance tests' source, put in front of the worker. The first real attempt saw only the test file names, never opened them
    and wrote count_word_frequency() where the tests import top_words()."""
    parts: list[str] = []
    for ref in spec.acceptance_test_refs:
        path = Path(worktree) / str(ref).split("::", 1)[0]
        try:
            parts.append(f"--- {ref}\n{path.read_text(encoding='utf-8')[:_ACCEPTANCE_CHARS]}")
        except OSError:
            continue
    return ("ACCEPTANCE TEST SOURCE (your code must make these pass; use the names they import):\n" + "\n".join(parts)) if parts else ""


_EXISTING_CHARS = 3000


def _existing_code(spec: LeafTaskSpec, worktree: str) -> str:
    """The modules already in the worktree that this task may not write (its verified dependencies, merged in before the attempt).

    Without their source the 7B coder answered 'blocked: src/wordfreq/core.py does not exist' on turn 1 although it was there: a contract
    line says what a function is called, not that the file is present."""
    root = Path(worktree)
    own = {p.replace("\\", "/") for p in spec.allowed_files}
    parts: list[str] = []
    budget = _EXISTING_CHARS
    for path in sorted((root / "src").rglob("*.py")) if (root / "src").is_dir() else []:
        rel = path.relative_to(root).as_posix()
        if path.name == "__init__.py" or budget <= 0:
            continue
        try:
            text = path.read_text(encoding="utf-8")[:budget]
        except OSError:
            continue
        budget -= len(text)
        note = " (YOURS: it already holds earlier work; add to it and keep every function that is there)" if rel in own else ""
        parts.append(f"--- {rel}{note}\n{text}")
    return ("EXISTING CODE (already in the repository, verified; import from it, do not rewrite what is not yours):\n" + "\n".join(parts)) if parts else ""


def _tool_loop(spec: LeafTaskSpec, worktree: str, gateway: ModelGateway, executor: ToolExecutor, context: str) -> str:
    header = _header(spec, "\n\n".join(part for part in (context, _existing_code(spec, worktree), _acceptance_source(spec, worktree)) if part), _TOOL_SHAPE)
    ran_tests = False
    wrote = False
    tests_failed = False
    last_failure = ""
    refused_blocks = 0
    policy = _policy(spec)
    calls: list[str] = []  # "Turn n: tool(args)" or a note, one per turn
    results: list[ShapedOutput | None] = []
    summary = ""  # older turns, compacted once the transcript reaches compact_at_pct of the window

    def transcript() -> str:
        texts = iter(policy.clear_stale([r for r in results if r is not None]))  # only the latest results stay in full
        body = [f"{c}\nResult: {next(texts)}" if r is not None else c for c, r in zip(calls, results, strict=True)]
        return header + (f"\n\nEarlier turns (summary): {summary}" if summary else "") + "".join(f"\n\n{b}" for b in body)

    deadline = _deadline(spec)
    for turn in range(1, spec.step_budget.max_turns + 1):
        if time.monotonic() > deadline:
            raise WorkerBlocked("SPEC_TOO_LARGE: the wall-clock budget for the attempt was exhausted")
        text = transcript()
        if policy.should_compact(len(text)) and len(calls) > policy.keep_recent:
            cut = len(calls) - policy.keep_recent
            old = [c if r is None else f"{c} -> {r.text[:300]}" for c, r in zip(calls[:cut], results[:cut], strict=True)]
            summary = compact_history(gateway, [summary, *old] if summary else old, max(64, spec.context_budget_tokens // 20))
            del calls[:cut], results[:cut]
            text = transcript()
        step = _repair_tool_step(_ask(gateway, text))
        action = step.get("action")
        trace_event("worker", "turn", task=str(spec.task_id), turn=turn, prompt_chars=len(text), action=action, tool=step.get("tool"), args=step.get("args"), message=step.get("message"), ran_tests=ran_tests)
        if action == "done":
            if spec.acceptance_test_refs and not ran_tests and turn < spec.step_budget.max_turns:
                calls.append(f"Turn {turn}: done was refused: call run_tests on the acceptance tests and make them pass first.")
                results.append(None)
                continue
            return f"tool_loop finished in {turn} step(s): {step.get('message', '')}"
        if action == "blocked":
            if (not wrote or tests_failed) and refused_blocks < MAX_BLOCK_REFUSALS and turn < spec.step_budget.max_turns:
                # a small model reports "blocked" at turn 1 without trying, or after the first failing test run instead of fixing the code
                refused_blocks += 1
                why = (
                    "the acceptance tests failed. Failure output:\n" + last_failure[-1500:] + "\nReply now with a write_file action holding the corrected COMPLETE file from your ALLOWED FILES, then run the tests again"
                    if tests_failed
                    else f"you have not written anything yet: write the ALLOWED FILES ({', '.join(spec.allowed_files)}), then run the tests"
                )
                calls.append(f"Turn {turn}: blocked was refused: {why}. Report blocked only after real attempts.")
                results.append(None)
                continue
            raise _blocked(step)
        if action != "tool" or not isinstance(step.get("tool"), str):
            calls.append(f"Turn {turn}: invalid action {action!r}; use tool, done or blocked.")
            results.append(None)
            continue
        args = step.get("args") if isinstance(step.get("args"), dict) else {}
        if step["tool"] == "run_tests":
            args = _test_selectors(spec, cast(dict[str, Any], args))
        calls.append(f"Turn {turn}: {step['tool']}({json.dumps(args)[:500]})")
        ran_tests = ran_tests or step["tool"] == "run_tests"
        wrote = wrote or step["tool"] == "write_file"
        if step["tool"] == "write_file":
            refused_blocks = 0  # a new write earns the coder new push-backs
            tests_failed = False  # the code changed: the earlier failure no longer says what the code does
        results.append(_shaped_tool(policy, executor, spec, str(step["tool"]), cast(dict[str, Any], args), worktree))
        shaped = results[-1]
        if step["tool"] == "run_tests":
            last_failure = str(getattr(shaped, "text", shaped))
            tests_failed = not last_failure.startswith("[ok] (0,")
        trace_event("worker", "tool_result", task=str(spec.task_id), turn=turn, tool=step["tool"], result=getattr(shaped, "text", shaped))
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
    model_role: str | None = None,
) -> str:
    """Run the bounded loop; return the worker self-report.

    model_role asks a different tier to do the thinking (the helper: a bigger model takes over a task the small coder could not do);
    the tools it may use stay those of the worker.

    code_exec is only used when the active sandbox tier is A; otherwise it falls back to tool_loop (and says why).
    """
    chosen: str = name
    if chosen == "code_exec" and str(executor.active_tier()) != "A":
        logger.warning("code_exec needs sandbox tier A (active: %s); falling back to tool_loop", executor.active_tier())
        chosen = "tool_loop"
    if chosen not in _STRATEGIES:
        raise ValueError(f"unknown worker strategy '{name}'")
    token = _MODEL_ROLE.set(model_role or "T2")
    try:
        return _STRATEGIES[chosen](spec, worktree, gateway, executor, context)
    finally:
        _MODEL_ROLE.reset(token)
