# FILE: src/asf/cli/commands/inbox.py
# ROLE: Implements `factory inbox list|show|answer`.
# ARCH REF: M1; p02 Decision Inbox; IF-03; IF-04
# OWNS: Argument parsing and output for this command group
# DOES NOT OWN: Business logic (lives in the imported modules)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/views/inbox_view.py: InboxView (rendering)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (IF-04 answers)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: EXIT_OK, EXIT_USER, default_output, guard, open_store, renderer_for (shared CLI plumbing)
#   - imports from src/asf/contracts/decisions.py: DecisionResolved (the answer)
#   - called by src/asf/cli/flows.py: inbox_answer
#   - called by src/asf/cli/app.py: register
#   - called by tests/cli/commands/test_inbox.py: inbox_list, inbox_show, inbox_answer, register
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Never run agents or keep execution state in the CLI; write commands to the command table (IF-05) and read state/events (M1 is a thin client).
#   6. Support --output rich|plain|json through Renderer; prompts only when stdin and stdout are TTYs, otherwise exit 2 naming the missing flags (D-13).
#   7. Exit codes: 0 success, 1 user/validation error, 2 environment problem.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/cli/commands/test_inbox.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/commands/inbox.py` and `uv run mypy src/asf/cli/commands/inbox.py` are clean.

from datetime import UTC, datetime

import typer

from asf.cli.context import EXIT_OK, EXIT_USER, default_output, guard, open_store, renderer_for
from asf.cli.views.inbox_view import InboxView
from asf.contracts.decisions import DecisionResolved
from asf.m5_shared.decisions.broker import DecisionBroker


def inbox_list(run_id: str | None, output: str = "rich") -> int:
    store = open_store(readonly=True)
    try:
        InboxView(renderer_for(output), run_id, store=store).render_once()
    finally:
        store.close()
    return EXIT_OK


def inbox_show(decision_id: str) -> int:
    renderer = renderer_for(default_output())
    store = open_store(readonly=True)
    try:
        view = InboxView(renderer, None, store=store)
        card = view.card(decision_id)
        if card is None:
            renderer.message(f"No pending decision '{decision_id}'. `factory inbox list` shows what is waiting.", "error")
            return EXIT_USER
        view.render_card(card)
    finally:
        store.close()
    return EXIT_OK


def inbox_answer(decision_id: str, choice: str | None, text: str | None) -> int:
    """Answer a decision (IF-04). Then `factory run resume RUN` continues the run."""
    renderer = renderer_for(default_output())
    store = open_store()
    try:
        card = InboxView(renderer, None, store=store).card(decision_id)
        if card is None:
            renderer.message(f"No pending decision '{decision_id}'. `factory inbox list` shows what is waiting.", "error")
            return EXIT_USER
        if choice is None and len(card.options) == 1:
            choice = card.options[0]
        if choice is None:
            renderer.message(f"Pick one option with --choice: {', '.join(card.options)}.", "error")
            return EXIT_USER
        if card.options and choice not in card.options:
            renderer.message(f"'{choice}' is not an option. Choose one of: {', '.join(card.options)}.", "error")
            return EXIT_USER
        DecisionBroker(store).resolve(
            DecisionResolved.model_validate(
                {"decision_id": decision_id, "choice": choice, "text": text, "answered_by": "user", "answered_at": datetime.now(UTC)}
            )
        )
        renderer.message(f"Answered {decision_id} with '{choice}'. Continue the run: factory run resume {card.run_id}", "success")
    finally:
        store.close()
    return EXIT_OK


def register(app: typer.Typer) -> None:
    """Attach the `inbox` command(s) to the root Typer app."""
    group = typer.Typer(help="Decisions waiting for you.", no_args_is_help=True)

    @group.command("list")
    def list_cmd(run_id: str | None = typer.Argument(None), output: str = typer.Option("rich", "--output", "-o")) -> None:
        raise typer.Exit(code=guard(lambda: inbox_list(run_id, output)))

    @group.command("show")
    def show_cmd(decision_id: str) -> None:
        raise typer.Exit(code=guard(lambda: inbox_show(decision_id)))

    @group.command("answer")
    def answer_cmd(
        decision_id: str,
        choice: str | None = typer.Option(None, "--choice", "-c", help="One of the decision's options"),
        text: str | None = typer.Option(None, "--text", "-t", help="Free text for a clarification"),
    ) -> None:
        raise typer.Exit(code=guard(lambda: inbox_answer(decision_id, choice, text)))

    app.add_typer(group, name="inbox")
