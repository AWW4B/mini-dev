# FILE: src/asf/web/server.py
# ROLE: Starlette app served by uvicorn on 127.0.0.1 only, with GET-only routes: page, static files, events page, SSE stream, details.
# ARCH REF: M1; p02; IF-18; D-14b; D-14b-S
# OWNS: HTTP routes, SSE with seq cursor (Last-Event-ID), bind-address enforcement
# DOES NOT OWN: Any write path (none exist)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/web/projection.py: Projection (view model)
#   - imports from src/asf/config/settings.py: load_settings (port)
#   - imports from src/asf/contracts/errors.py: PolicyDenied (bind refusal)
#   - called by src/asf/cli/commands/web.py: serve
#   - called by tests/web/test_server.py: check_bind_host, create_app, serve, ALLOWED_BIND_HOST, ROUTE_PATHS
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. serve() raises PolicyDenied for any host other than the exact string "127.0.0.1" (also refuse "localhost", "0.0.0.0", "::", "::1").
#   9. Serve src/asf/web/static/index.html, src/asf/web/static/app.js and src/asf/web/static/style.css as the only static files.
#   10. Every route uses methods=["GET"] (HEAD implied); there are no POST/PUT/PATCH/DELETE routes or WebSocket endpoints.
#   11. Serve static files from importlib.resources(asf.web/static); set Content-Security-Policy default-src 'self'.
#   12. Import starlette/uvicorn inside functions so the base install imports this module; exit hint: `uv sync --extra web`.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; binding to any address other than 127.0.0.1; write endpoints; opening state.db read-write; inline script tags
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/web/test_server.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/web/server.py` and `uv run mypy src/asf/web/server.py` are clean.

from typing import Any

ALLOWED_BIND_HOST: str = "127.0.0.1"
ROUTE_PATHS: tuple[str, ...] = ("/", "/static/{path:path}", "/api/runs/{run_id}/events", "/api/runs/{run_id}/stream", "/api/details/{ref}")


def check_bind_host(host: str) -> None:
    """Raise PolicyDenied unless host == ALLOWED_BIND_HOST."""
    raise NotImplementedError


def create_app(run_id: str | None) -> Any:
    """Return the Starlette application (GET routes only)."""
    raise NotImplementedError


def serve(run_id: str | None, host: str = ALLOWED_BIND_HOST, port: int = 8765) -> None:
    raise NotImplementedError
