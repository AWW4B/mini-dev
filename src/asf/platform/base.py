# FILE: src/asf/platform/base.py
# ROLE: Declares the PlatformAdapter and SandboxBackend protocols every OS implementation satisfies.
# ARCH REF: FR-4 (one platform-adapter interface); D-15; D-20; D-21; IF-14 sandbox tier
# OWNS: The adapter interface and sandbox spec/result shapes
# DOES NOT OWN: Any OS-specific implementation (windows.py, linux.py, fallback.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tools.py: SandboxTier (tier enum)
#   - called by src/asf/platform/linux.py: PlatformAdapter, SandboxBackend, SandboxSpec, ProcessResult
#   - called by src/asf/platform/windows.py: PlatformAdapter, SandboxBackend, SandboxSpec, ProcessResult
#   - called by src/asf/platform/fallback.py: PlatformAdapter, SandboxBackend, SandboxSpec, ProcessResult
#   - called by src/asf/platform/sandbox_bwrap.py: PlatformAdapter, SandboxBackend, SandboxSpec, ProcessResult
#   - called by src/asf/platform/sandbox_srt.py: PlatformAdapter, SandboxBackend, SandboxSpec, ProcessResult
#   - called by src/asf/platform/sandbox_jobobject.py: PlatformAdapter, SandboxBackend, SandboxSpec, ProcessResult
#   - called by src/asf/platform/select.py: PlatformAdapter, SandboxBackend, SandboxSpec, ProcessResult
#   - called by src/asf/m2_request/repository_intake.py: SandboxSpec
#   - called by tests/platform/test_base.py: SandboxSpec, ProcessResult, SandboxBackend, PlatformAdapter
#   - called by src/asf/m4_execution/verification/gate.py: ProcessResult, SandboxSpec
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Keep these as typing.Protocol classes and Pydantic models only; no OS calls here.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/platform/test_base.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/platform/base.py` and `uv run mypy src/asf/platform/base.py` are clean.

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from asf.contracts.tools import SandboxTier


class SandboxSpec(BaseModel):
    argv: list[str]
    cwd: Path
    writable_paths: list[Path]
    readable_paths: list[Path]
    network: bool = False
    timeout_s: int = 120
    env: dict[str, str] = {}
    extra_fds: list[int] = []


class ProcessResult(BaseModel):
    exit_code: int
    stdout: bytes
    stderr: bytes
    timed_out: bool
    duration_ms: int


class SandboxBackend(Protocol):
    name: str
    tier: SandboxTier

    def available(self) -> bool: ...

    def run(self, spec: SandboxSpec) -> ProcessResult: ...


class PlatformAdapter(Protocol):
    name: str

    def sandbox(self) -> SandboxBackend: ...

    def run_process(self, argv: list[str], cwd: Path, timeout_s: int, env: dict[str, str] | None = None) -> ProcessResult: ...

    def kill_tree(self, pid: int) -> None: ...

    def lock_file(self, path: Path, timeout_s: float) -> object:
        """Return a context manager holding an exclusive lock on path."""
        ...

    def resolve_within(self, root: Path, candidate: str) -> Path:
        """Resolve candidate under root, rejecting symlink and junction escapes (PolicyDenied)."""
        ...

    def install_interrupt_handler(self, on_interrupt: object) -> None: ...

    def detach(self, argv: list[str], log_path: Path) -> int: ...
