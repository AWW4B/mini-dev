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

import asyncio
import importlib.resources
import json
from collections.abc import AsyncIterator
from typing import Any

from asf.contracts.errors import PolicyDenied
from asf.web.projection import Projection

ALLOWED_BIND_HOST: str = "127.0.0.1"
ROUTE_PATHS: tuple[str, ...] = ("/", "/static/{path:path}", "/api/runs/{run_id}/events", "/api/runs/{run_id}/stream", "/api/details/{ref}")

STATIC_FILES = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8", "style.css": "text/css; charset=utf-8"}
CONTENT_SECURITY_POLICY = "default-src 'self'"
STREAM_POLL_S = 1.0


def check_bind_host(host: str) -> None:
    """Raise PolicyDenied unless host == ALLOWED_BIND_HOST (the exact string: not localhost, not 0.0.0.0, not ::)."""
    if host != ALLOWED_BIND_HOST:
        raise PolicyDenied(f"The viewer may only listen on {ALLOWED_BIND_HOST}, not '{host}': it has no login, so it must never be reachable from the network.")


def _static_bytes(name: str) -> bytes:
    return importlib.resources.files("asf.web").joinpath("static", name).read_bytes()


def create_app(run_id: str | None) -> Any:
    """Return the Starlette application (GET routes only)."""
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response, StreamingResponse
    from starlette.routing import Route

    def projection_for(requested: str) -> Projection:
        return Projection(run_id if requested in ("current", "") else requested)

    def secure(response: Response) -> Response:
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    async def index(request: Request) -> Response:
        return secure(Response(_static_bytes("index.html"), media_type=STATIC_FILES["index.html"]))

    async def static(request: Request) -> Response:
        name = request.path_params["path"]
        if name not in STATIC_FILES:
            return secure(JSONResponse({"error": "not found"}, status_code=404))
        return secure(Response(_static_bytes(name), media_type=STATIC_FILES[name]))

    async def events(request: Request) -> Response:
        try:
            after = int(request.query_params.get("after", "0"))
            limit = int(request.query_params.get("limit", "200"))
        except ValueError:
            return secure(JSONResponse({"error": "after and limit must be integers"}, status_code=400))
        include_internal = request.query_params.get("internal") in ("1", "true")
        try:
            view = projection_for(request.path_params["run_id"])
        except (FileNotFoundError, LookupError) as err:
            return secure(JSONResponse({"error": str(err)}, status_code=404))
        try:
            return secure(JSONResponse(view.page(after, limit, include_internal)))
        finally:
            view.close()

    async def stream(request: Request) -> Response:
        try:
            after = int(request.query_params.get("after", "0"))
        except ValueError:
            return secure(JSONResponse({"error": "after must be an integer"}, status_code=400))
        include_internal = request.query_params.get("internal") in ("1", "true")
        once = request.query_params.get("once") in ("1", "true")  # one batch, then end (for clients without streaming)
        requested = request.path_params["run_id"]

        async def generate() -> AsyncIterator[str]:
            cursor = after
            while not await request.is_disconnected():
                try:
                    view = projection_for(requested)
                except (FileNotFoundError, LookupError) as err:
                    yield f"event: error\ndata: {json.dumps({'error': str(err)})}\n\n"
                    return
                try:
                    page = view.page(cursor, 200, include_internal)
                finally:
                    view.close()
                if page["next_seq"] > cursor or once:
                    cursor = page["next_seq"]
                    yield f"id: {cursor}\nevent: page\ndata: {json.dumps(page)}\n\n"
                if once:
                    return
                await asyncio.sleep(STREAM_POLL_S)

        return secure(StreamingResponse(generate(), media_type="text/event-stream"))

    async def details(request: Request) -> Response:
        try:
            view = projection_for("current")
        except (FileNotFoundError, LookupError) as err:
            return secure(JSONResponse({"error": str(err)}, status_code=404))
        try:
            result = view.detail(request.path_params["ref"])
        finally:
            view.close()
        return secure(JSONResponse(result, status_code=404 if "error" in result else 200))

    routes = [
        Route("/", index, methods=["GET"]),
        Route("/static/{path:path}", static, methods=["GET"]),
        Route("/api/runs/{run_id}/events", events, methods=["GET"]),
        Route("/api/runs/{run_id}/stream", stream, methods=["GET"]),
        Route("/api/details/{ref}", details, methods=["GET"]),
    ]
    return Starlette(routes=routes)


def serve(run_id: str | None, host: str = ALLOWED_BIND_HOST, port: int = 8765) -> None:
    check_bind_host(host)
    try:
        import uvicorn
    except ImportError as err:
        raise ImportError("The web viewer needs the web extra. Install it with: uv sync --extra web") from err
    uvicorn.run(create_app(run_id), host=host, port=port, log_level="warning")
