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

import os
import secrets
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from pydantic import BaseModel

from asf.contracts.errors import SandboxUnavailable
from asf.m5_shared.tools.codeexec.channel import FramedChannel
from asf.m5_shared.tools.codeexec.facade_gen import generate_facade
from asf.m5_shared.tools.executor import ToolExecutor
from asf.platform.select import get_platform


class CodeExecResult(BaseModel):
    ok: bool
    summary: str
    stdout_ref: str | None
    stderr_ref: str | None
    tool_calls: int
    duration_ms: int


def execute_code(
    executor: ToolExecutor,
    script: str,
    role: str,
    task_id: str | None,
    allowed_files: list[str],
    timeout_s: int = 120,
) -> CodeExecResult:
    platform = get_platform()
    sandbox = platform.sandbox()
    if str(getattr(sandbox, "tier", "")) != "A":
        raise SandboxUnavailable(
            f"Code execution requires sandbox tier A, but current tier is {getattr(sandbox, 'tier', 'unknown')}"
        )

    start_time = time.monotonic()
    tool_calls = 0

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Generate facade
        specs = executor.registry.specs_for(role)
        facade_content = generate_facade(specs)
        (tmp_path / "tools.py").write_text(facade_content, encoding="utf-8")

        # 2. Write agent script
        script_path = tmp_path / "script.py"
        script_path.write_text(script, encoding="utf-8")

        # 3. Setup channel
        tag = secrets.token_hex(16)
        r_child, w_parent = os.pipe()
        r_parent, w_child = os.pipe()

        try:
            os.set_inheritable(r_child, True)
            os.set_inheritable(w_child, True)
        except Exception as _inh_err:  # noqa: BLE001
            _ = _inh_err

        parent_reader = os.fdopen(r_parent, "rb")
        parent_writer = os.fdopen(w_parent, "wb")
        parent_channel = FramedChannel(parent_reader, parent_writer, tag)

        stop_event = threading.Event()

        def _serve_channel() -> None:
            nonlocal tool_calls
            while not stop_event.is_set():
                try:
                    req = parent_channel.receive(timeout_s=0.2)
                except (ValueError, OSError):
                    break
                if req is None:
                    continue
                tool_calls += 1
                t_name = req.get("tool", "")
                t_args = req.get("args", {})
                req_id = req.get("id", "")
                try:
                    inv = SimpleNamespace(
                        tool=t_name,
                        args=t_args,
                        role=role,
                        task_id=task_id,
                        workspace_dir=str(tmp_path),
                        via_code_exec=True,
                    )
                    res = executor.invoke(cast(Any, inv), allowed_files)
                    if getattr(res, "status", "ok") != "ok":
                        parent_channel.send(
                            "tool_response",
                            req_id,
                            {"error": getattr(res, "output", "tool execution failed")},
                        )
                    else:
                        parent_channel.send(
                            "tool_response",
                            req_id,
                            {"result": getattr(res, "output", "")},
                        )
                except Exception as exc:  # noqa: BLE001
                    parent_channel.send("tool_response", req_id, {"error": str(exc)})

        server_thread = threading.Thread(target=_serve_channel, daemon=True)
        server_thread.start()

        env = {
            "ASF_EXEC_TAG": tag,
            "ASF_EXEC_FD_IN": str(r_child),
            "ASF_EXEC_FD_OUT": str(w_child),
            "PYTHONPATH": str(tmp_path),
        }

        readable = [tmp_path] + [Path(p) for p in allowed_files]
        writable = [tmp_path]

        spec = SimpleNamespace(
            argv=[sys.executable, str(script_path)],
            cwd=tmp_path,
            readable_paths=readable,
            writable_paths=writable,
            network=False,
            timeout_s=timeout_s,
            env=env,
            extra_fds=[r_child, w_child],
        )

        try:
            proc_res = sandbox.run(cast(Any, spec))
        finally:
            stop_event.set()
            try:
                os.close(w_child)
            except Exception as _err:  # noqa: BLE001
                _ = _err
            try:
                os.close(r_child)
            except Exception as _err:  # noqa: BLE001
                _ = _err
            server_thread.join(timeout=0.5)
            parent_channel.close()

        duration_ms = int((time.monotonic() - start_time) * 1000)
        exit_code = getattr(proc_res, "exit_code", 1)
        ok = exit_code == 0
        raw_out = getattr(proc_res, "stdout", b"")
        raw_err = getattr(proc_res, "stderr", b"")
        stdout_str = raw_out.decode("utf-8", errors="replace") if isinstance(raw_out, bytes) else str(raw_out)
        stderr_str = raw_err.decode("utf-8", errors="replace") if isinstance(raw_err, bytes) else str(raw_err)

        if ok:
            summary = f"Script succeeded (exit code 0). Made {tool_calls} tool call(s)."
        else:
            summary = f"Script failed (exit code {exit_code}). Stderr: {stderr_str[:300]}"

        return CodeExecResult(
            ok=ok,
            summary=summary,
            stdout_ref=stdout_str if stdout_str else None,
            stderr_ref=stderr_str if stderr_str else None,
            tool_calls=tool_calls,
            duration_ms=duration_ms,
        )
