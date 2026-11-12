# FILE: src/asf/contracts/control.py
# ROLE: Defines RunControl (IF-05) commands and the CancelSignal / RunFlag broadcast (IF-06).
# ARCH REF: p04 Run Control; IF-05; IF-06; D-15
# OWNS: Command shapes
# DOES NOT OWN: Command delivery (state_store command table)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/ids.py: CommandId, RunId, TaskId (typed ids)
#   - called by src/asf/m5_shared/state_store/store.py: RunControl
#   - called by src/asf/m3_orchestration/run_control.py: RunControl, RunCommand, CancelSignal
#   - called by src/asf/m4_execution/scheduler.py: CancelSignal
#   - called by src/asf/cli/run_controls.py: RunControl, RunCommand
#   - called by tests/contracts/test_control.py: RunCommand, RunControl, CancelSignal
#   - called by tests/m3_orchestration/test_run_control.py: RunControl
#   - called by tests/cli/test_run_controls.py: RunCommand
#   - called by src/asf/cli/commands/run.py: RunCommand
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. This file is declarations only: Pydantic models, enums and type aliases. Add field validators only where the docstring of a field states a constraint.
#   6. Every model must round-trip through model_dump_json() / model_validate_json() unchanged; the JSON Schema exported from these models is the published contract (D-39: no hand-written JSON).
#   7. Changing a field name or type is a contract change: stop and report instead.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; business logic; I/O; imports from asf.m1-m5 packages, asf.cli, asf.web or asf.platform
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/contracts/test_control.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/contracts/control.py` and `uv run mypy src/asf/contracts/control.py` are clean.

from enum import StrEnum

from pydantic import BaseModel

from asf.contracts.ids import CommandId, RunId, TaskId


class RunCommand(StrEnum):
    PAUSE = "pause"
    RESUME = "resume"
    ABORT = "abort"
    CANCEL_TASK = "cancel_task"


class RunControl(BaseModel):
    """IF-05: written to the command table by the CLI, polled by the supervisor (D-15)."""
    command_id: CommandId
    run_id: RunId
    command: RunCommand
    task_id: TaskId | None = None


class CancelSignal(BaseModel):
    """IF-06: broadcast to M2, M4 and the M5 runtime."""
    run_id: RunId
    scope: str
    command: RunCommand
    task_id: TaskId | None = None
