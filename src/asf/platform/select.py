# FILE: src/asf/platform/select.py
# ROLE: Returns the PlatformAdapter for the running OS (cached).
# ARCH REF: FR-4; D-20
# OWNS: Adapter selection
# DOES NOT OWN: Adapter behaviour
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/platform/base.py: PlatformAdapter, SandboxBackend, SandboxSpec, ProcessResult (platform protocols)
#   - imports from src/asf/platform/linux.py: LinuxPlatform (Linux)
#   - imports from src/asf/platform/windows.py: WindowsPlatform (Windows)
#   - imports from src/asf/platform/fallback.py: FallbackPlatform (other)
#   - called by src/asf/m5_shared/workspace/workspace.py: get_platform
#   - called by src/asf/m5_shared/runtime/backends.py: get_platform
#   - called by src/asf/m5_shared/tools/policy.py: get_platform
#   - called by src/asf/m5_shared/tools/executor.py: get_platform
#   - called by src/asf/m5_shared/tools/builtin_tools.py: get_platform
#   - called by src/asf/m5_shared/tools/codeexec/runner.py: get_platform
#   - called by src/asf/m5_shared/context/repo_index.py: get_platform
#   - called by src/asf/doctor/checks.py: get_platform
#   - called by src/asf/m2_request/repository_intake.py: get_platform
#   - called by src/asf/m3_orchestration/run_control.py: get_platform
#   - called by src/asf/m4_execution/verification/gate.py: get_platform
#   - called by tests/platform/test_select.py: get_platform
#   - called by src/asf/m4_execution/worker/strategies.py: get_platform
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Select by sys.platform ("win32" -> Windows, "linux" -> Linux, otherwise fallback); cache with functools.cache.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/platform/test_select.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/platform/select.py` and `uv run mypy src/asf/platform/select.py` are clean.

import functools
import sys

from asf.platform.base import PlatformAdapter, ProcessResult, SandboxBackend, SandboxSpec  # noqa: F401
from asf.platform.fallback import FallbackPlatform
from asf.platform.linux import LinuxPlatform
from asf.platform.windows import WindowsPlatform


@functools.cache
def get_platform() -> PlatformAdapter:
    if sys.platform == "win32":
        return WindowsPlatform()
    if sys.platform.startswith("linux"):
        return LinuxPlatform()
    return FallbackPlatform()
