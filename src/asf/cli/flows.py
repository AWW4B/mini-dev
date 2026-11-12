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
#   - imports from src/asf/cli/context.py: EXIT_OK, EXIT_USER, open_store (waiting runs and pending decisions)
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

import json
from pathlib import Path

from asf.cli.commands.doctor import doctor
from asf.cli.commands.inbox import inbox_answer
from asf.cli.commands.models import models_init
from asf.cli.commands.run import run_resume, run_start
from asf.cli.context import EXIT_OK, EXIT_USER, open_store
from asf.cli.ui.menus import ask_text, choose, confirm, is_interactive

_MODES = ["(let the factory decide)", "new_build", "debug", "feature", "refactor", "test_generation", "code_docs"]


def _need_terminal() -> bool:
    if not is_interactive():
        print("This guided flow needs a terminal. Use the commands with options instead (see `factory --help`).")
        return False
    return True


def flow_new_run() -> int:
    if not _need_terminal():
        return 2
    text = ask_text("What should be built or changed? (describe it in your own words)", multiline=True)
    files = [Path(p.strip().strip('"')) for p in ask_text("Requirements documents (paths separated by commas, or empty)", default="").split(",") if p.strip()]
    repo = ask_text("Existing repository (path or git URL, or empty for a new project)", default="").strip() or None
    mode = choose("What kind of work is this?", _MODES, default=_MODES[0])
    local_tests = confirm("If the planning model is unavailable, may a local model draft the acceptance tests (you approve them first)?", default=False)
    if not confirm("Start the run now?", default=True):
        return EXIT_OK
    return run_start(text, files, repo, None if mode == _MODES[0] else mode, None, [], [], local_tests, False)


def _waiting_runs() -> list[tuple[str, str]]:
    store = open_store(readonly=True)
    try:
        rows = store.conn.execute("SELECT run_id, status FROM runs WHERE status IN ('PAUSED', 'AWAITING_DECISION', 'RUNNING') ORDER BY last_activity DESC").fetchall()
    finally:
        store.close()
    return [(str(r["run_id"]), str(r["status"])) for r in rows]


def flow_resume() -> int:
    if not _need_terminal():
        return 2
    runs = _waiting_runs()
    if not runs:
        print("No run is waiting to be resumed.")
        return EXIT_OK
    labels = {f"{run_id}  [{status}]": run_id for run_id, status in runs}
    return run_resume(labels[choose("Which run should continue?", list(labels))])


def flow_inbox_answer() -> int:
    if not _need_terminal():
        return 2
    store = open_store(readonly=True)
    try:
        rows = store.conn.execute("SELECT decision_id, payload FROM decisions WHERE status = 'PENDING' ORDER BY created_at, rowid").fetchall()
    finally:
        store.close()
    if not rows:
        print("No decisions are waiting for you.")
        return EXIT_OK
    cards = {str(r["decision_id"]): json.loads(r["payload"]) for r in rows}
    labels = {f"{did}: {card['question'][:70]}": did for did, card in cards.items()}
    chosen = labels[choose("Which decision?", list(labels))]
    card = cards[chosen]
    options = list(card.get("options", []))
    answer = choose(card["question"], options) if options else None
    text = ask_text("Anything to add? (optional)", default="") or None
    code = inbox_answer(chosen, answer, text)
    if code == EXIT_OK and confirm("Continue the run now?", default=True):
        return run_resume(str(card["run_id"]))
    return code


def flow_models_setup() -> int:
    if not _need_terminal():
        return 2
    code = models_init(True)
    return code if code != EXIT_OK or not confirm("Run the environment check now?", default=True) else doctor("rich")


def flow_doctor() -> int:
    return doctor("rich")


def main_menu() -> int:
    """Shown by bare `factory` on a TTY."""
    if not is_interactive():
        print("Run `factory --help` to see the commands.")
        return EXIT_USER
    actions = {
        "Start a new run": flow_new_run,
        "Continue a run": flow_resume,
        "Answer a decision": flow_inbox_answer,
        "Set up models": flow_models_setup,
        "Check the environment": flow_doctor,
    }
    while True:
        picked = choose("What would you like to do?", [*actions, "Quit"])
        if picked == "Quit":
            return EXIT_OK
        code = actions[picked]()
        if code not in (EXIT_OK,):
            print(f"(finished with exit code {code})")
