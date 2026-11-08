# FILE: src/asf/platform/sandbox_bwrap.py
# ROLE: Tier-A sandbox on Linux using bubblewrap directly.
# ARCH REF: D-20; D-21 tier A; D-22 network off
# OWNS: bwrap argument construction and execution
# DOES NOT OWN: Choosing the backend (linux.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/platform/base.py: PlatformAdapter, SandboxBackend, SandboxSpec, ProcessResult (platform protocols)
#   - called by src/asf/platform/linux.py: BubblewrapSandbox
#   - called by tests/platform/test_sandbox_bwrap.py: BubblewrapSandbox
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Build the bwrap argv: --unshare-all (network unless spec.network), --die-with-parent, read-only binds for readable_paths, binds for writable_paths, --chdir cwd.
#   9. Locate bwrap with shutil.which; available() is False if missing (doctor reports the apt/pacman package).
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/platform/test_sandbox_bwrap.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/platform/sandbox_bwrap.py` and `uv run mypy src/asf/platform/sandbox_bwrap.py` are clean.

from asf.platform.base import ProcessResult, SandboxSpec


class BubblewrapSandbox:
    name = "bubblewrap"
    tier = "A"

    def available(self) -> bool:
        raise NotImplementedError

    def build_argv(self, spec: SandboxSpec) -> list[str]:
        raise NotImplementedError

    def run(self, spec: SandboxSpec) -> ProcessResult:
        raise NotImplementedError
