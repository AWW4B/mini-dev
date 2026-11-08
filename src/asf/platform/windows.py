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

from pathlib import Path

from asf.platform.base import ProcessResult, SandboxBackend


class WindowsPlatform:
    name = "windows"

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
