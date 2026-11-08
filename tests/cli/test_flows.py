# FILE: tests/cli/test_flows.py
# ROLE: Tests that prove src/asf/cli/flows.py meets its DONE WHEN conditions.
# ARCH REF: M1; D-12 guided flows; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/flows.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/flows.py: flow_new_run, flow_resume, flow_inbox_answer, flow_models_setup, flow_doctor, main_menu (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/test_flows.py` on Windows and Linux once src/asf/cli/flows.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/test_flows.py` and `uv run mypy tests/cli/test_flows.py` are clean.


from asf.cli.flows import flow_doctor, flow_inbox_answer, flow_models_setup, flow_new_run, flow_resume, main_menu  # noqa: F401


def test_flow_new_run_meets_contract() -> None:
    """Prove flow_new_run behaves as declared in src/asf/cli/flows.py."""
    raise NotImplementedError("write this test before implementing flow_new_run")

def test_flow_resume_meets_contract() -> None:
    """Prove flow_resume behaves as declared in src/asf/cli/flows.py."""
    raise NotImplementedError("write this test before implementing flow_resume")

def test_flow_inbox_answer_meets_contract() -> None:
    """Prove flow_inbox_answer behaves as declared in src/asf/cli/flows.py."""
    raise NotImplementedError("write this test before implementing flow_inbox_answer")

def test_flow_models_setup_meets_contract() -> None:
    """Prove flow_models_setup behaves as declared in src/asf/cli/flows.py."""
    raise NotImplementedError("write this test before implementing flow_models_setup")

def test_flow_doctor_meets_contract() -> None:
    """Prove flow_doctor behaves as declared in src/asf/cli/flows.py."""
    raise NotImplementedError("write this test before implementing flow_doctor")

def test_main_menu_meets_contract() -> None:
    """Prove main_menu behaves as declared in src/asf/cli/flows.py."""
    raise NotImplementedError("write this test before implementing main_menu")
