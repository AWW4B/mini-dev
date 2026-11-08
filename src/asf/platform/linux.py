# FILE: src/asf/platform/linux.py
# ROLE: Linux implementation of PlatformAdapter (Debian-family and Arch).
# ARCH REF: FR-4; D-15; D-20 bubblewrap; D-21
# OWNS: Linux process groups, fcntl/portalocker locks, SIGINT handling, bubblewrap/srt sandbox selection
# DOES NOT OWN: Windows behaviour
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/platform/base.py: PlatformAdapter, SandboxBackend, SandboxSpec, ProcessResult (platform protocols)
#   - imports from src/asf/platform/sandbox_bwrap.py: BubblewrapSandbox (tier A)
#   - imports from src/asf/platform/sandbox_srt.py: SrtSandbox (tier A alternative)
#   - imports from src/asf/platform/fallback.py: StaticOnlySandbox (tier C)
#   - imports from src/asf/contracts/errors.py: PolicyDenied (escape rejection)
#   - called by src/asf/platform/select.py: LinuxPlatform
#   - called by tests/platform/test_linux.py: LinuxPlatform
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Prefer bubblewrap; use srt when configured; otherwise StaticOnlySandbox (tier C).
#   9. Kill whole process groups (start children with start_new_session=True).
#   10. detach() is a stub that raises NotSupportedOnPlatform until D-15 detach is implemented.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/platform/test_linux.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/platform/linux.py` and `uv run mypy src/asf/platform/linux.py` are clean.

from pathlib import Path

from asf.platform.base import ProcessResult, SandboxBackend


class LinuxPlatform:
    name = "linux"

    def sandbox(self) -> SandboxBackend:
        raise NotImplementedError

    def run_process(self, argv: list[str], cwd: Path, timeout_s: int, env: dict[str, str] | None = None) -> ProcessResult:
        raise NotImplementedError

    def kill_tree(self, pid: int) -> None:
        raise NotImplementedError

    def lock_file(self, path: Path, timeout_s: float) -> object:
        raise NotImplementedError

    def resolve_within(self, root: Path, candidate: str) -> Path:
        raise NotImplementedError

    def install_interrupt_handler(self, on_interrupt: object) -> None:
        raise NotImplementedError

    def detach(self, argv: list[str], log_path: Path) -> int:
        raise NotImplementedError
