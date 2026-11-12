# FILE: src/asf/cli/commands/report.py
# ROLE: Implements `factory report`: prints or writes the final run report (deliverables, traceability matrix, decisions, cost).
# ARCH REF: M1; p02; p04 Deliver report
# OWNS: Argument parsing and output for this command group
# DOES NOT OWN: Business logic (lives in the imported modules)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (read-only queries / command rows)
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (report blob)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: EXIT_OK, EXIT_USER, guard, open_store, renderer_for, resolve_run_id (shared CLI plumbing)
#   - called by src/asf/cli/app.py: register
#   - called by tests/cli/commands/test_report.py: report, register
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Never run agents or keep execution state in the CLI; write commands to the command table (IF-05) and read state/events (M1 is a thin client).
#   9. Support --output rich|plain|json through Renderer; prompts only when stdin and stdout are TTYs, otherwise exit 2 naming the missing flags (D-13).
#   10. Exit codes: 0 success, 1 user/validation error, 2 environment problem.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/cli/commands/test_report.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/commands/report.py` and `uv run mypy src/asf/cli/commands/report.py` are clean.

import json
from pathlib import Path

import typer

from asf.cli.context import EXIT_OK, EXIT_USER, guard, open_store, renderer_for, resolve_run_id
from asf.m5_shared.state_store.store import StateStore
from asf.m5_shared.workspace.blobs import BlobStore


def _report_ref(store: StateStore, run_id: str) -> str | None:
    """The report blob of a finished run: the run_completed event (relayed) or, before the relay, the outbox row."""
    conn = store.conn
    for sql in (
        "SELECT payload FROM events WHERE run_id = ? AND kind = 'run_completed' ORDER BY seq DESC LIMIT 1",
        "SELECT payload FROM outbox WHERE run_id = ? ORDER BY id DESC",
    ):
        for row in conn.execute(sql, (run_id,)):
            data = json.loads(row["payload"])
            if data.get("kind") == "run_completed" and data.get("payload", {}).get("report_ref"):
                return str(data["payload"]["report_ref"])
    return None


def report(run_id: str, out: Path | None = None) -> int:
    """Print the final report (requirements, acceptance, decision log, cost) or write it to ``out``."""
    renderer = renderer_for("plain")
    store = open_store(readonly=True)
    try:
        chosen = resolve_run_id(store, run_id or None)
        ref = _report_ref(store, chosen)
        run = store.conn.execute("SELECT status, cost, cost_estimated FROM runs WHERE run_id = ?", (chosen,)).fetchone()
    finally:
        store.close()
    if ref is None:
        status = run["status"] if run is not None else "unknown"
        renderer.message(f"Run {chosen} has no report yet (status: {status}). A report is written when the run completes.", "error")
        return EXIT_USER
    text = BlobStore().get(ref).decode("utf-8", errors="replace")
    cost = f"{run['cost']:.4f}{' (estimated)' if run['cost_estimated'] else ''}" if run is not None else "unknown"
    text += f"\n\n## Cost\n{cost}\n"
    if out is not None:
        out.write_text(text, encoding="utf-8")
        renderer.message(f"Report written to {out}", "success")
    else:
        renderer.out.write(text)
    return EXIT_OK


def register(app: typer.Typer) -> None:
    """Attach the `report` command(s) to the root Typer app."""

    @app.command("report", help="Print or save the final report of a run.")
    def report_cmd(
        run_id: str = typer.Argument("", help="Run id (default: the latest run)"),
        out: Path | None = typer.Option(None, "--out", help="Write the report to this file"),
    ) -> None:
        raise typer.Exit(code=guard(lambda: report(run_id, out)))
