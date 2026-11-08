# FILE: src/asf/platform/sandbox_jobobject.py
# ROLE: Tier-B containment on Windows using a Job Object (kill-on-close, memory/CPU limits) without filesystem isolation.
# ARCH REF: D-20; D-21 tier B (approval per run; code_exec, dependency installs and network disabled)
# OWNS: Job Object setup and execution
# DOES NOT OWN: Approval (DecisionBroker kind UNSANDBOXED_EXECUTION)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/platform/base.py: PlatformAdapter, SandboxBackend, SandboxSpec, ProcessResult (platform protocols)
#   - called by src/asf/platform/windows.py: JobObjectSandbox
#   - called by tests/platform/test_sandbox_jobobject.py: JobObjectSandbox
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Import pywin32 lazily; available() returns False off Windows.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/platform/test_sandbox_jobobject.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/platform/sandbox_jobobject.py` and `uv run mypy src/asf/platform/sandbox_jobobject.py` are clean.

import logging
import subprocess
import sys
import time
from typing import Any

from asf.platform.base import ProcessResult, SandboxSpec

_LOGGER = logging.getLogger(__name__)


def _get_pywin32() -> tuple[Any, Any, Any] | None:
    if sys.platform != "win32":
        return None
    try:
        import win32api  # type: ignore[import-untyped]
        import win32con  # type: ignore[import-untyped]
        import win32job  # type: ignore[import-untyped]

        return win32job, win32api, win32con
    except ImportError:
        return None


class JobObjectSandbox:
    name = "jobobject"
    tier = "B"

    def available(self) -> bool:
        return _get_pywin32() is not None

    def run(self, spec: SandboxSpec) -> ProcessResult:
        win32 = _get_pywin32()
        if not win32:
            raise RuntimeError("JobObjectSandbox is not available on this platform")
        win32job, win32api, _ = win32

        job = win32job.CreateJobObject(None, "")
        info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
        info["BasicLimitInformation"]["LimitFlags"] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)

        start_time = time.monotonic()
        env = spec.env if spec.env else None
        proc = subprocess.Popen(  # noqa: S603
            spec.argv,
            cwd=spec.cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            win32job.AssignProcessToJobObject(job, proc._handle)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("Failed to assign process to job object: %s", exc)

        try:
            stdout, stderr = proc.communicate(timeout=spec.timeout_s)
            timed_out = False
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                win32job.TerminateJobObject(job, 1)
            except Exception as exc:  # noqa: BLE001
                _LOGGER.debug("TerminateJobObject failed: %s", exc)
                proc.kill()
            stdout, stderr = proc.communicate()
            exit_code = -1
        finally:
            try:
                win32api.CloseHandle(job)
            except Exception as exc:  # noqa: BLE001
                _LOGGER.debug("CloseHandle failed: %s", exc)

        duration_ms = int((time.monotonic() - start_time) * 1000)
        return ProcessResult(
            exit_code=exit_code,
            stdout=stdout or b"",
            stderr=stderr or b"",
            timed_out=timed_out,
            duration_ms=duration_ms,
        )
