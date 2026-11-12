# FILE: src/asf/cli/commands/stats.py
# ROLE: Implements `factory stats`: call/tool/limit metrics per run, role, model and strategy.
# ARCH REF: M1; p10; D-24; D-19 comparability
# OWNS: Argument parsing and output for this command group
# DOES NOT OWN: Business logic (lives in the imported modules)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/metrics/collector.py: MetricsCollector (IF-19)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: EXIT_OK, EXIT_USER, guard, open_store, renderer_for, resolve_run_id (shared CLI plumbing)
#   - called by src/asf/cli/app.py: register
#   - called by tests/cli/commands/test_stats.py: stats, register
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
# DONE WHEN: (1) tests/cli/commands/test_stats.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/commands/stats.py` and `uv run mypy src/asf/cli/commands/stats.py` are clean.

import typer

from asf.cli.context import EXIT_OK, EXIT_USER, guard, open_store, renderer_for, resolve_run_id
from asf.m5_shared.metrics.collector import MetricsCollector

_GROUPS = {"role": "role", "model": "model", "provider": "provider", "strategy": "strategy", "task": "task_id"}


def stats(run_id: str | None, by: str = "role", output: str = "rich") -> int:
    """Model calls per run, grouped by role, model, provider, strategy or task (estimated tokens are flagged)."""
    renderer = renderer_for(output)
    column = _GROUPS.get(by)
    if column is None:
        renderer.message(f"Cannot group by '{by}'. Use one of: {', '.join(_GROUPS)}.", "error")
        return EXIT_USER
    store = open_store(readonly=True)
    try:
        chosen = resolve_run_id(store, run_id)
        rows = store.conn.execute(
            f"SELECT coalesce(nullif({column}, ''), '(unknown)') AS grp, COUNT(*) AS calls, sum(input_tokens) AS tin, sum(output_tokens) AS tout, "  # noqa: S608 - column comes from a fixed map
            "sum(cost) AS cost, avg(duration_ms) AS latency, max(estimated) AS est "
            "FROM call_metrics WHERE run_id = ? GROUP BY grp ORDER BY cost DESC, calls DESC",
            (chosen,),
        ).fetchall()
        snap = MetricsCollector(store).snapshot(chosen)
    finally:
        store.close()
    table = [[r["grp"], r["calls"], r["tin"], r["tout"], f"{r['cost']:.4f}{' EST' if r['est'] else ''}", f"{r['latency']:.0f} ms"] for r in rows]
    table.append(["TOTAL", int(snap.values["calls"]), int(snap.values["input_tokens"]), int(snap.values["output_tokens"]), f"{snap.values['cost']:.4f}", ""])
    renderer.table(f"Model calls of run {chosen} by {by}", [by, "calls", "tokens in", "tokens out", "cost", "avg latency"], table)
    return EXIT_OK


def register(app: typer.Typer) -> None:
    """Attach the `stats` command(s) to the root Typer app."""

    @app.command("stats", help="Model-call statistics by role, model, strategy or task.")
    def stats_cmd(
        run_id: str | None = typer.Argument(None),
        by: str = typer.Option("role", "--by", help="role | model | provider | strategy | task"),
        output: str = typer.Option("rich", "--output", "-o"),
    ) -> None:
        raise typer.Exit(code=guard(lambda: stats(run_id, by, output)))
