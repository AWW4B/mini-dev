# FILE: src/asf/cli/commands/events.py
# ROLE: Implements `factory events export` (JSONL + CSV, OTel GenAI attribute names).
# ARCH REF: M1; p10; D-25
# OWNS: Argument parsing and output for this command group
# DOES NOT OWN: Business logic (lives in the imported modules)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/events/event_log.py: EventLog (events)
#   - imports from src/asf/m5_shared/metrics/collector.py: MetricsCollector (CSV tables)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: EXIT_OK, EXIT_USER, guard, open_store, renderer_for, resolve_run_id (shared CLI plumbing)
#   - called by src/asf/cli/app.py: register
#   - called by tests/cli/commands/test_events.py: events_export, register
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
# DONE WHEN: (1) tests/cli/commands/test_events.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/commands/events.py` and `uv run mypy src/asf/cli/commands/events.py` are clean.

import json
from pathlib import Path

import typer

from asf.cli.context import EXIT_OK, EXIT_USER, guard, open_store, renderer_for, resolve_run_id
from asf.m5_shared.events.event_log import EventLog
from asf.m5_shared.metrics.collector import MetricsCollector

_OTEL = {
    "model": "gen_ai.request.model",
    "provider": "gen_ai.system",
    "tokens_in": "gen_ai.usage.input_tokens",
    "tokens_out": "gen_ai.usage.output_tokens",
    "tool": "gen_ai.tool.name",
}


def _otel_attributes(payload: dict[str, object]) -> dict[str, object]:
    """Map our payload keys onto the OpenTelemetry GenAI attribute names where they exist."""
    return {_OTEL[k]: v for k, v in payload.items() if k in _OTEL}


def events_export(run_id: str, dest: Path, fmt: str = "jsonl") -> int:
    """Export a run: JSONL (one event per line, with OTel GenAI attributes) or CSV tables (calls, tools, limits)."""
    renderer = renderer_for("plain")
    if fmt not in ("jsonl", "csv"):
        renderer.message(f"Unknown format '{fmt}'. Use jsonl or csv.", "error")
        return EXIT_USER
    store = open_store(readonly=True)
    try:
        chosen = resolve_run_id(store, run_id or None)
        if fmt == "csv":
            files = MetricsCollector(store).export_csv(chosen, dest)
            renderer.message(f"Wrote {len(files)} CSV file(s) to {dest}", "success")
            return EXIT_OK
        dest.parent.mkdir(parents=True, exist_ok=True)
        log, cursor, count = EventLog(store.conn), 0, 0
        with dest.open("w", encoding="utf-8", newline="\n") as handle:
            while True:
                batch = log.read(chosen, after_seq=cursor, limit=500)
                if not batch:
                    break
                for event in batch:
                    cursor = max(cursor, event.seq)
                    record = event.model_dump(mode="json")
                    record["attributes"] = _otel_attributes(event.payload)
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                    count += 1
    finally:
        store.close()
    renderer.message(f"Wrote {count} event(s) to {dest}", "success")
    return EXIT_OK


def register(app: typer.Typer) -> None:
    """Attach the `events` command(s) to the root Typer app."""
    group = typer.Typer(help="Export a run's events.", no_args_is_help=True)

    @group.command("export")
    def export_cmd(
        dest: Path,
        run_id: str = typer.Argument("", help="Run id (default: the latest run)"),
        fmt: str = typer.Option("jsonl", "--format", help="jsonl | csv"),
    ) -> None:
        raise typer.Exit(code=guard(lambda: events_export(run_id, dest, fmt)))

    app.add_typer(group, name="events")
