# FILE: src/asf/cli/run_controls.py
# ROLE: Writes IF-05 RunControl rows to the command table; the run supervisor applies them.
# ARCH REF: M1; p02 Run Controls; IF-05; D-15
# OWNS: Command row creation
# DOES NOT OWN: Applying commands (m3_orchestration/run_control.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/control.py: RunControl, RunCommand (IF-05)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (read-only queries / command rows)
#   - called by src/asf/cli/commands/run.py: send_command
#   - called by tests/cli/test_run_controls.py: send_command
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/cli/test_run_controls.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/run_controls.py` and `uv run mypy src/asf/cli/run_controls.py` are clean.

from asf.contracts.control import RunCommand


def send_command(run_id: str, command: RunCommand, task_id: str | None = None) -> str:
    """Insert the command row; return command_id."""
    raise NotImplementedError
