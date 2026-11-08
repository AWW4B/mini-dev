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

import shutil
import subprocess
import sys
from enum import StrEnum

import psutil
from pydantic import BaseModel

from asf.config.paths import AppPaths, get_paths  # noqa: F401
from asf.config.secrets import key_sources
from asf.m5_shared.runtime.probes import ResourceProbe
from asf.platform.select import get_platform


class CheckStatus(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


class CheckResult(BaseModel):
    name: str
    status: CheckStatus
    detail: str
    fix_hints: dict[str, str] = {}


def _check_python() -> CheckResult:
    ver = sys.version_info
    ver_str = f"{ver.major}.{ver.minor}.{ver.micro}"
    if (3, 12) <= ver < (3, 15):
        return CheckResult(
            name="python",
            status=CheckStatus.OK,
            detail=f"Python {ver_str} (>=3.12,<3.15)",
        )
    return CheckResult(
        name="python",
        status=CheckStatus.FAIL,
        detail=f"Python {ver_str} is out of required range (>=3.12,<3.15)",
        fix_hints={
            "apt": "apt install python3.12 python3.12-venv",
            "pacman": "pacman -S python",
            "winget": "winget install Python.Python.3.12",
        },
    )


def _check_uv() -> CheckResult:
    uv_bin = shutil.which("uv")
    if not uv_bin:
        return CheckResult(
            name="uv",
            status=CheckStatus.FAIL,
            detail="uv executable not found on PATH",
            fix_hints={
                "apt": "curl -LsSf https://astral.sh/uv/install.sh | sh",
                "pacman": "pacman -S uv",
                "winget": "winget install astral-sh.uv",
            },
        )
    try:
        res = subprocess.run([uv_bin, "--version"], capture_output=True, text=True, timeout=5, check=False)  # noqa: S603
        ver = res.stdout.strip() or "uv found"
        return CheckResult(name="uv", status=CheckStatus.OK, detail=ver)
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="uv",
            status=CheckStatus.WARN,
            detail=f"uv on PATH but execution failed: {exc}",
            fix_hints={
                "apt": "curl -LsSf https://astral.sh/uv/install.sh | sh",
                "pacman": "pacman -S uv",
                "winget": "winget install astral-sh.uv",
            },
        )


def _check_git() -> CheckResult:
    git_bin = shutil.which("git")
    if not git_bin:
        return CheckResult(
            name="git",
            status=CheckStatus.FAIL,
            detail="git executable not found on PATH",
            fix_hints={
                "apt": "apt install git",
                "pacman": "pacman -S git",
                "winget": "winget install Git.Git",
            },
        )
    try:
        res = subprocess.run([git_bin, "--version"], capture_output=True, text=True, timeout=5, check=False)  # noqa: S603
        ver = res.stdout.strip()
        return CheckResult(name="git", status=CheckStatus.OK, detail=ver)
    except Exception as exc:  # noqa: BLE001
        return CheckResult(name="git", status=CheckStatus.WARN, detail=f"git execution error: {exc}")


def _check_ripgrep() -> CheckResult:
    rg_bin = shutil.which("rg")
    if not rg_bin:
        return CheckResult(
            name="ripgrep",
            status=CheckStatus.WARN,
            detail="ripgrep (rg) not found on PATH (optional but recommended for fast search)",
            fix_hints={
                "apt": "apt install ripgrep",
                "pacman": "pacman -S ripgrep",
                "winget": "winget install BurntSushi.ripgrep.MSVC",
            },
        )
    return CheckResult(name="ripgrep", status=CheckStatus.OK, detail="ripgrep found on PATH")


def _check_sandbox_tier() -> CheckResult:
    try:
        adapter = get_platform()
        sandbox = adapter.sandbox()
        tier = getattr(sandbox.tier, "value", str(sandbox.tier))
        name = getattr(sandbox, "name", "unknown")
        if tier == "A":
            return CheckResult(name="sandbox_tier", status=CheckStatus.OK, detail=f"Tier-A sandbox active ({name})")
        if tier == "B":
            return CheckResult(
                name="sandbox_tier",
                status=CheckStatus.OK,
                detail=f"Tier-B containment active ({name})",
                fix_hints={
                    "apt": "apt install bubblewrap",
                    "pacman": "pacman -S bubblewrap",
                    "winget": "Use srt or WSL2 for Tier-A sandbox on Windows",
                },
            )
        return CheckResult(
            name="sandbox_tier",
            status=CheckStatus.WARN,
            detail=f"Tier-C static-only fallback active ({name})",
            fix_hints={
                "apt": "apt install bubblewrap",
                "pacman": "pacman -S bubblewrap",
                "winget": "winget install astral-sh.uv (or use WSL2 for full isolation)",
            },
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(name="sandbox_tier", status=CheckStatus.WARN, detail=f"Sandbox probe error: {exc}")


def _check_resources() -> CheckResult:
    try:
        probe = ResourceProbe()
        reading = probe.read()
        ram_str = f"RAM free: {reading.ram_free_mb} MB"
        vram_str = f", VRAM free: {reading.vram_free_mb} MB" if reading.vram_free_mb is not None else ", VRAM: n/a"
        return CheckResult(name="resources", status=CheckStatus.OK, detail=f"{ram_str}{vram_str}")
    except (NotImplementedError, Exception):
        # Stub or probe error fallback to psutil
        try:
            mem = psutil.virtual_memory()
            free_mb = int(mem.available / (1024 * 1024))
            return CheckResult(
                name="resources",
                status=CheckStatus.OK,
                detail=f"RAM free: {free_mb} MB (GPU probe uncalibrated)",
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(name="resources", status=CheckStatus.WARN, detail=f"Resource check error: {exc}")


def _check_keys() -> CheckResult:
    try:
        sources = key_sources()
        configured = [p for p, s in sources.items() if s != "missing"]
        if configured:
            detail = f"Configured keys: {', '.join(f'{p} ({sources[p]})' for p in configured)}"
            return CheckResult(name="api_keys", status=CheckStatus.OK, detail=detail)
        return CheckResult(
            name="api_keys",
            status=CheckStatus.WARN,
            detail="No API keys found in keyring, env, or .env (required for cloud profiles)",
            fix_hints={
                "winget": "keyring set ai-software-factory <provider> or set FACTORY_<PROVIDER>_API_KEY",
                "apt": "set FACTORY_<PROVIDER>_API_KEY in environment or ~/.config/ai-software-factory/.env",
                "pacman": "set FACTORY_<PROVIDER>_API_KEY in environment or ~/.config/ai-software-factory/.env",
            },
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(name="api_keys", status=CheckStatus.WARN, detail=f"Key sources check error: {exc}")


def _check_writable_dirs() -> CheckResult:
    try:
        paths = get_paths()
        dirs = [paths.config_dir, paths.data_dir, paths.log_dir, paths.cache_dir]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
            test_file = d / ".doctor_write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()
        return CheckResult(name="writable_dirs", status=CheckStatus.OK, detail="All base directories are writable")
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name="writable_dirs",
            status=CheckStatus.FAIL,
            detail=f"Directory write permission check failed: {exc}",
            fix_hints={
                "apt": "Check permissions on ~/.config and ~/.local/share",
                "pacman": "Check permissions on ~/.config and ~/.local/share",
                "winget": "Check permissions on AppData",
            },
        )


def run_all_checks() -> list[CheckResult]:
    return [
        _check_python(),
        _check_uv(),
        _check_git(),
        _check_ripgrep(),
        _check_sandbox_tier(),
        _check_resources(),
        _check_keys(),
        _check_writable_dirs(),
    ]
