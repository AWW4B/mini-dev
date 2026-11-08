# FILE: src/asf/platform/fallback.py
# ROLE: Safe fallback adapter and the tier-C StaticOnlySandbox used when no real sandbox exists.
# ARCH REF: FR-4 safe fallback; D-21 tier C
# OWNS: Conservative portable behaviour
# DOES NOT OWN: Any real isolation
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/platform/base.py: PlatformAdapter, SandboxBackend, SandboxSpec, ProcessResult (platform protocols)
#   - imports from src/asf/contracts/tools.py: SandboxTier (tier)
#   - imports from src/asf/contracts/errors.py: SandboxUnavailable (refusal)
#   - called by src/asf/platform/linux.py: StaticOnlySandbox
#   - called by src/asf/platform/windows.py: StaticOnlySandbox
#   - called by src/asf/platform/select.py: FallbackPlatform
#   - called by tests/platform/test_fallback.py: FallbackPlatform, StaticOnlySandbox
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. StaticOnlySandbox.run must never execute agent code; it raises SandboxUnavailable so the gate suspends.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/platform/test_fallback.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/platform/fallback.py` and `uv run mypy src/asf/platform/fallback.py` are clean.

import signal
import subprocess
import sys
import time
from pathlib import Path

import portalocker
import psutil

from asf.contracts.errors import SandboxUnavailable
from asf.contracts.tools import SandboxTier
from asf.platform.base import PlatformAdapter, ProcessResult, SandboxBackend, SandboxSpec  # noqa: F401


class FallbackPlatform:
    name = "fallback"

    def sandbox(self) -> SandboxBackend:
        return StaticOnlySandbox()

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
            raise SandboxUnavailable(f"Candidate {candidate!r} escapes root {root!r}") from err
        return target

    def install_interrupt_handler(self, on_interrupt: object) -> None:
        if callable(on_interrupt):
            def _handler(signum: int, frame: object) -> None:
                on_interrupt()

            signal.signal(signal.SIGINT, _handler)

    def detach(self, argv: list[str], log_path: Path) -> int:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "ab") as log_file:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                proc = subprocess.Popen(  # noqa: S603
                    argv,
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=log_file,
                    creationflags=creationflags,
                )
            else:
                proc = subprocess.Popen(  # noqa: S603
                    argv,
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=log_file,
                    start_new_session=True,
                )
            return proc.pid


class StaticOnlySandbox:
    name = "static-only"
    tier: SandboxTier = SandboxTier.C

    def available(self) -> bool:
        return True

    def run(self, spec: object) -> ProcessResult:
        raise SandboxUnavailable("StaticOnlySandbox does not execute code; a tier-A or tier-B sandbox is required.")
