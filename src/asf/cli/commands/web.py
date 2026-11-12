# FILE: src/asf/cli/commands/web.py
# ROLE: Implements `factory web [RUN]`: starts the read-only viewer on 127.0.0.1.
# ARCH REF: M1; p02 Active Group Chat; D-14b
# OWNS: Argument parsing and output for this command group
# DOES NOT OWN: Business logic (lives in the imported modules)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/web/server.py: serve (viewer)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: EXIT_ENV, EXIT_OK, guard, renderer_for (shared CLI plumbing)
#   - called by src/asf/cli/app.py: register
#   - called by tests/cli/commands/test_web.py: web, register
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
# DONE WHEN: (1) tests/cli/commands/test_web.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/commands/web.py` and `uv run mypy src/asf/cli/commands/web.py` are clean.

import importlib.util
import threading
import webbrowser

import typer

from asf.cli.context import EXIT_ENV, EXIT_OK, guard, renderer_for
from asf.web.server import ALLOWED_BIND_HOST, serve

DEFAULT_PORT = 8765


def web(run_id: str | None, port: int | None = None, open_browser: bool = True) -> int:
    """Exit 2 with an install hint when the [web] extra is missing."""
    renderer = renderer_for("plain")
    missing = [m for m in ("starlette", "uvicorn") if importlib.util.find_spec(m) is None]
    if missing:
        renderer.message(f"The web viewer needs the web extra ({', '.join(missing)} missing). Install it with: uv sync --extra web", "error")
        return EXIT_ENV
    chosen = port or DEFAULT_PORT
    url = f"http://{ALLOWED_BIND_HOST}:{chosen}/"
    renderer.message(f"Read-only viewer at {url} (Ctrl+C stops it; the run is not affected)", "success")
    if open_browser:
        threading.Timer(1.0, webbrowser.open, [url]).start()
    try:
        serve(run_id, ALLOWED_BIND_HOST, chosen)
    except KeyboardInterrupt:
        renderer.message("viewer stopped")
    return EXIT_OK


def register(app: typer.Typer) -> None:
    """Attach the `web` command(s) to the root Typer app."""

    @app.command("web", help="Open the read-only web viewer (needs the web extra).")
    def web_cmd(
        run_id: str | None = typer.Argument(None),
        port: int | None = typer.Option(None, "--port"),
        open_browser: bool = typer.Option(True, "--open/--no-open", help="Open the browser"),
    ) -> None:
        raise typer.Exit(code=guard(lambda: web(run_id, port, open_browser)))
