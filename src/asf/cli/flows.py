# FILE: src/asf/cli/flows.py
# ROLE: Guided flows (new run, resume, inbox answer, models setup, doctor) that ask questions and then call the same command functions.
# ARCH REF: M1; D-12 guided flows
# OWNS: Question sequences
# DOES NOT OWN: Command behaviour
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/ui/menus.py: choose, ask_text, confirm, is_interactive (prompts)
#   - imports from src/asf/cli/commands/run.py: run_start, run_resume (commands)
#   - imports from src/asf/cli/commands/inbox.py: inbox_answer (commands)
#   - imports from src/asf/cli/commands/models.py: models_init (commands)
#   - imports from src/asf/cli/commands/doctor.py: doctor (commands)
#   - called by src/asf/cli/app.py: main_menu
#   - called by tests/cli/test_flows.py: flow_new_run, flow_resume, flow_inbox_answer, flow_models_setup, flow_doctor, main_menu
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/cli/test_flows.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/flows.py` and `uv run mypy src/asf/cli/flows.py` are clean.

def flow_new_run() -> int:
    raise NotImplementedError


def flow_resume() -> int:
    raise NotImplementedError


def flow_inbox_answer() -> int:
    raise NotImplementedError


def flow_models_setup() -> int:
    raise NotImplementedError


def flow_doctor() -> int:
    raise NotImplementedError


def main_menu() -> int:
    """Shown by bare `factory` on a TTY."""
    raise NotImplementedError
