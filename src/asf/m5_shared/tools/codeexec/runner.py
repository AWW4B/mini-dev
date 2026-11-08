# FILE: src/asf/m5_shared/tools/codeexec/runner.py
# ROLE: Runs an agent-written Python script in a tier-A sandbox, serving its tool requests through the ToolExecutor.
# ARCH REF: M5; p12; D-19; D-19a; D-21 (never tier B/C)
# OWNS: execute_code lifecycle
# DOES NOT OWN: Policy decisions (executor)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/tools/executor.py: ToolExecutor (every call goes through invoke())
#   - imports from src/asf/m5_shared/tools/codeexec/channel.py: FramedChannel (framing)
#   - imports from src/asf/m5_shared/tools/codeexec/facade_gen.py: generate_facade (facade)
#   - imports from src/asf/platform/select.py: get_platform (platform adapter)
#   - imports from src/asf/contracts/errors.py: SandboxUnavailable (error types)
#   - called by src/asf/m4_execution/worker/strategies.py: execute_code
#   - called by tests/m5_shared/tools/codeexec/test_runner.py: CodeExecResult, execute_code
#   - emits/consumes: TOOL_CALLED/TOOL_RESULT per call (emitted by ToolExecutor with via_code_exec=True); STEP_STARTED for the script
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Refuse to run (SandboxUnavailable) unless the active tier is A.
#   9. Capture script stdout/stderr separately from the channel; return only a summary to the model.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/tools/codeexec/test_runner.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/tools/codeexec/runner.py` and `uv run mypy src/asf/m5_shared/tools/codeexec/runner.py` are clean.

from pydantic import BaseModel

from asf.m5_shared.tools.executor import ToolExecutor


class CodeExecResult(BaseModel):
    ok: bool
    summary: str
    stdout_ref: str | None
    stderr_ref: str | None
    tool_calls: int
    duration_ms: int


def execute_code(executor: ToolExecutor, script: str, role: str, task_id: str | None, allowed_files: list[str], timeout_s: int = 120) -> CodeExecResult:
    raise NotImplementedError
