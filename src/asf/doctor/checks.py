# FILE: src/asf/doctor/checks.py
# ROLE: Individual environment checks for `factory doctor`.
# ARCH REF: FR-4 doctor; D-45; D-20 tier report; D-09 baseline warning
# OWNS: Each check and its per-distro fix hint
# DOES NOT OWN: Report writing (report.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/platform/select.py: get_platform (sandbox tier)
#   - imports from src/asf/config/secrets.py: key_sources (D-38)
#   - imports from src/asf/config/paths.py: AppPaths, get_paths (cross-platform base directories)
#   - imports from src/asf/m5_shared/runtime/probes.py: ResourceProbe (RAM/VRAM)
#   - called by src/asf/doctor/report.py: CheckResult, CheckStatus
#   - called by src/asf/cli/commands/doctor.py: run_all_checks
#   - called by tests/doctor/test_checks.py: CheckStatus, CheckResult, run_all_checks
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Locate tools with shutil.which only; run versions with argument lists and a short timeout.
#   9. Every failing check carries fix hints for apt (Debian/Ubuntu), pacman (Arch) and winget/manual (Windows).
#   10. Checks: python range, uv, lock in sync (uv lock --check), git, ripgrep (optional), bubblewrap/srt, Node (only if MCP or Pyright configured), GPU via NVML, VRAM/RAM, runtime reachable, sandbox tier, key sources, model baseline, MCP commands, writable dirs.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/doctor/test_checks.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/doctor/checks.py` and `uv run mypy src/asf/doctor/checks.py` are clean.

from enum import StrEnum

from pydantic import BaseModel


class CheckStatus(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


class CheckResult(BaseModel):
    name: str
    status: CheckStatus
    detail: str
    fix_hints: dict[str, str] = {}


def run_all_checks() -> list[CheckResult]:
    raise NotImplementedError
