# FILE: src/asf/m3_orchestration/run_control.py
# ROLE: Foreground supervisor loop: polls the command table, applies pause/resume/abort/cancel-task and broadcasts CancelSignal.
# ARCH REF: M3; p04 Run Control; IF-05 RunControl; IF-06 CancelSignal; D-15
# OWNS: Command handling and Ctrl+C clean pause
# DOES NOT OWN: Writing commands (CLI)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/control.py: RunControl, RunCommand, CancelSignal (IF-05/IF-06)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (IF-16 state)
#   - imports from src/asf/platform/select.py: get_platform (platform adapter)
#   - imports from src/asf/m4_execution/scheduler.py: TaskScheduler (receives CancelSignal)
#   - imports from src/asf/m5_shared/runtime/local_runtime.py: LocalRuntime (lease revocation)
#   - called by tests/m3_orchestration/test_run_control.py: RunSupervisor
#   - emits/consumes: emits CANCELLED and STATE_CHANGED events
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Validate command_id idempotently; install the Ctrl+C handler via the platform adapter so an interrupt becomes a clean PAUSE.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/test_run_control.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/run_control.py` and `uv run mypy src/asf/m3_orchestration/run_control.py` are clean.

from asf.contracts.control import CancelSignal, RunControl


class RunSupervisor:
    def __init__(self, run_id: str) -> None:
        raise NotImplementedError

    def apply(self, command: RunControl) -> CancelSignal | None:
        raise NotImplementedError

    def loop(self) -> None:
        """Poll commands and advisories until the run is terminal or paused."""
        raise NotImplementedError
