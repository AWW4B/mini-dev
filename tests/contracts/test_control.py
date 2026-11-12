# FILE: tests/contracts/test_control.py
# ROLE: Tests that prove src/asf/contracts/control.py meets its DONE WHEN conditions.
# ARCH REF: p04 Run Control; IF-05; IF-06; D-15; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/control.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/control.py: RunCommand, RunControl, CancelSignal (unit under test)
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use the tmp_path fixture or the fake_paths fixture for every filesystem location.
#   6. Use the fakes from tests/conftest.py instead of real GPUs, networks, sandboxes or model providers unless the test is marked needs_gpu, needs_network or needs_sandbox.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; real API keys; network access in unmarked tests; sleeping for timing (use the fake clock)
# ERRORS: Failures surface as pytest assertion failures.
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_control.py` on Windows and Linux once src/asf/contracts/control.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_control.py` and `uv run mypy tests/contracts/test_control.py` are clean.



import pytest
from pydantic import ValidationError

from asf.contracts.control import CancelSignal, RunCommand, RunControl


def test_commands_are_the_four_supported_values() -> None:
    assert {c.value for c in RunCommand} == {"pause", "resume", "abort", "cancel_task"}


def test_run_control_task_id_defaults_to_none() -> None:
    ctl = RunControl.model_validate({"command_id": "c1", "run_id": "r1", "command": "pause"})
    assert ctl.command is RunCommand.PAUSE
    assert ctl.task_id is None


def test_cancel_task_command_carries_a_task_id() -> None:
    ctl = RunControl.model_validate({"command_id": "c1", "run_id": "r1", "command": "cancel_task", "task_id": "t9"})
    assert ctl.command is RunCommand.CANCEL_TASK
    assert ctl.task_id == "t9"


def test_unknown_command_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RunControl.model_validate({"command_id": "c1", "run_id": "r1", "command": "reboot"})
    with pytest.raises(ValidationError):
        CancelSignal.model_validate({"run_id": "r1", "scope": "run", "command": "reboot"})


@pytest.mark.parametrize("missing", ["command_id", "run_id", "command"])
def test_run_control_required_fields(missing: str) -> None:
    data = {"command_id": "c1", "run_id": "r1", "command": "abort"}
    del data[missing]
    with pytest.raises(ValidationError):
        RunControl.model_validate(data)


def test_cancel_signal_round_trip() -> None:
    sig = CancelSignal.model_validate({"run_id": "r1", "scope": "task", "command": "cancel_task", "task_id": "t2"})
    assert CancelSignal.model_validate_json(sig.model_dump_json()) == sig
