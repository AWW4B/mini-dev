# FILE: src/asf/platform/windows.py
# ROLE: Windows implementation of PlatformAdapter.
# ARCH REF: FR-4; D-15; D-20 (srt or Job Object); D-21
# OWNS: Job Objects, CTRL_C handling, msvcrt/portalocker locks, junction-aware path resolution, sandbox selection
# DOES NOT OWN: Linux behaviour
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/platform/base.py: PlatformAdapter, SandboxBackend, SandboxSpec, ProcessResult (platform protocols)
#   - imports from src/asf/platform/sandbox_srt.py: SrtSandbox (tier A)
#   - imports from src/asf/platform/sandbox_jobobject.py: JobObjectSandbox (tier B)
#   - imports from src/asf/platform/fallback.py: StaticOnlySandbox (tier C)
#   - imports from src/asf/contracts/errors.py: PolicyDenied (escape rejection)
#   - called by src/asf/platform/select.py: WindowsPlatform
#   - called by tests/platform/test_windows.py: WindowsPlatform
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Import pywin32 modules lazily inside functions so this file imports on Linux for tests.
#   9. Prefer srt if installed, else Job Object (tier B); report WSL2 as the recommended full-isolation route.
#   10. Reject paths that traverse junctions or reparse points out of root.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/platform/test_windows.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/platform/windows.py` and `uv run mypy src/asf/platform/windows.py` are clean.

import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import cast

import portalocker
import psutil

from asf.contracts.errors import PolicyDenied
from asf.platform.base import PlatformAdapter, ProcessResult, SandboxBackend, SandboxSpec  # noqa: F401
from asf.platform.fallback import StaticOnlySandbox
from asf.platform.sandbox_jobobject import JobObjectSandbox
from asf.platform.sandbox_srt import SrtSandbox


class WindowsPlatform:
    name = "windows"

    def sandbox(self) -> SandboxBackend:
        srt = SrtSandbox()
        if srt.available():
            return cast(SandboxBackend, srt)
        job = JobObjectSandbox()
        if job.available():
            return cast(SandboxBackend, job)
        return cast(SandboxBackend, StaticOnlySandbox())

    def run_process(self, argv: list[str], cwd: Path, timeout_s: int, env: dict[str, str] | None = None) -> ProcessResult:
        start_time = time.monotonic()
        try:
            completed = subprocess.run(  # noqa: S603
                argv,
                cwd=cwd,
                timeout=timeout_s,
                env=env,
                capture_output=True,
                check=False,
            )
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return ProcessResult(
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                timed_out=False,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return ProcessResult(
                exit_code=-1,
                stdout=exc.stdout or b"",
                stderr=exc.stderr or b"",
                timed_out=True,
                duration_ms=duration_ms,
            )

    def kill_tree(self, pid: int) -> None:
        try:
            proc = psutil.Process(pid)
            for child in proc.children(recursive=True):
                try:
                    child.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    def lock_file(self, path: Path, timeout_s: float) -> object:
        return portalocker.Lock(str(path), timeout=timeout_s)

    def resolve_within(self, root: Path, candidate: str) -> Path:
        root_resolved = root.resolve()
        target = (root / candidate).resolve()
        try:
            target.relative_to(root_resolved)
        except ValueError as err:
            raise PolicyDenied(f"Candidate {candidate!r} escapes root {root!r}") from err

        curr = root_resolved
        rel_parts = target.relative_to(root_resolved).parts
        for part in rel_parts:
            curr = curr / part
            is_junc = hasattr(curr, "is_junction") and curr.is_junction()
            if curr.is_symlink() or is_junc:
                real = curr.resolve()
                try:
                    real.relative_to(root_resolved)
                except ValueError as err:
                    raise PolicyDenied(f"Junction or symlink escape detected in candidate: {candidate!r}") from err
        return target

    def install_interrupt_handler(self, on_interrupt: object) -> None:
        if sys.platform == "win32":
            try:
                import win32api  # type: ignore[import-untyped]
                import win32con  # type: ignore[import-untyped]

                def _handler(ctrl_type: int) -> bool:
                    if ctrl_type in (win32con.CTRL_C_EVENT, win32con.CTRL_BREAK_EVENT):
                        if callable(on_interrupt):
                            on_interrupt()
                        return True
                    return False

                win32api.SetConsoleCtrlHandler(_handler, True)
                return
            except ImportError:
                pass

        if callable(on_interrupt):
            def _sig_handler(signum: int, frame: object) -> None:
                on_interrupt()

            signal.signal(signal.SIGINT, _sig_handler)

    def detach(self, argv: list[str], log_path: Path) -> int:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "ab") as log_file:
            creationflags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            proc = subprocess.Popen(  # noqa: S603
                argv,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=log_file,
                creationflags=creationflags,
            )
            return proc.pid
