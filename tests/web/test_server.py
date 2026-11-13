# FILE: tests/web/test_server.py
# ROLE: Tests that prove src/asf/web/server.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02; IF-18; D-14b; D-14b-S; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/web/server.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/web/server.py: check_bind_host, create_app, serve, ALLOWED_BIND_HOST, ROUTE_PATHS (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
#   - imports from src/asf/contracts/errors.py: PolicyDenied (expected refusal)
#   - imports from src/asf/contracts/events.py: EventEnvelope (event fixtures)
#   - imports from src/asf/m5_shared/events/event_log.py: EventLog (stores the events)
#   - imports from src/asf/m5_shared/state_store/schema.py: migrate (a real database layout)
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (detail blobs)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/web/test_server.py` on Windows and Linux once src/asf/web/server.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/web/test_server.py` and `uv run mypy tests/web/test_server.py` are clean.

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from asf.contracts.errors import PolicyDenied
from asf.web.server import ALLOWED_BIND_HOST, ROUTE_PATHS, check_bind_host, create_app, serve  # noqa: F401

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def test_allowed_host_is_loopback_ipv4() -> None:
    assert ALLOWED_BIND_HOST == "127.0.0.1"


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "::1", "localhost", "192.168.1.10", "10.0.0.5", " 127.0.0.1", "127.0.0.2"])
def test_server_refuses_any_bind_address_except_loopback(host: str) -> None:
    with pytest.raises(PolicyDenied):
        check_bind_host(host)


@pytest.mark.parametrize("host", ["0.0.0.0", "localhost", "::"])
def test_serve_refuses_before_starting_anything(host: str) -> None:
    with pytest.raises(PolicyDenied):
        serve(None, host=host)


def test_loopback_bind_is_accepted() -> None:
    check_bind_host("127.0.0.1")


def test_no_write_routes_exist() -> None:
    pytest.importorskip("starlette")
    app = create_app(None)
    for route in app.routes:
        methods = set(getattr(route, "methods", None) or set())
        assert not (methods & WRITE_METHODS), f"write method on {getattr(route, 'path', route)}"
        assert type(route).__name__ != "WebSocketRoute"


def test_the_routes_are_exactly_the_declared_ones() -> None:
    pytest.importorskip("starlette")
    assert tuple(route.path for route in create_app(None).routes) == ROUTE_PATHS


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    pytest.importorskip("starlette")
    from starlette.testclient import TestClient

    from asf.contracts.events import EventEnvelope
    from asf.m5_shared.events.event_log import EventLog
    from asf.m5_shared.state_store.schema import migrate
    from asf.m5_shared.workspace.blobs import BlobStore

    monkeypatch.setenv("FACTORY_HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    path = tmp_path / ".factory" / "state.db"
    path.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(path), autocommit=False)
    conn.row_factory = sqlite3.Row
    migrate(conn)
    with conn:
        conn.execute("INSERT INTO runs (run_id, project_id, status, version, created_at, last_activity, cost, cost_estimated, payload) VALUES ('run1', 'p', 'DONE', 1, 't', 't', 0, 0, '{}')")
    ref = BlobStore().put(b"the test log")
    EventLog(conn).append(
        [
            EventEnvelope.model_validate(
                {
                    "event_id": f"e{i}", "run_id": "run1", "seq": 0, "ts": "2026-11-12T10:00:00+00:00", "actor": {"kind": "agent", "role": "worker", "name": "W"},
                    "kind": "tool_result", "correlation_id": "c", "payload": {"tool": "run_tests", "summary": f"step {i}", "duration_ms": 1, "output_ref": ref},
                }
            )
            for i in range(1, 4)
        ]
    )
    conn.close()
    test_client = TestClient(create_app("run1"))
    test_client.ref = ref  # type: ignore[attr-defined]
    return test_client


def test_the_page_and_the_three_static_files_are_served_with_a_content_security_policy(client: Any) -> None:
    for url, kind in (("/", "text/html"), ("/static/app.js", "javascript"), ("/static/style.css", "text/css"), ("/static/index.html", "text/html")):
        response = client.get(url)
        assert response.status_code == 200 and kind in response.headers["content-type"], url
        assert response.headers["content-security-policy"] == "default-src 'self'" and response.headers["x-content-type-options"] == "nosniff"
    assert "Factory Viewer" in client.get("/").text


@pytest.mark.parametrize("path", ["/static/../../pyproject.toml", "/static/server.py", "/static/..%2F..%2Fpyproject.toml", "/static/other.txt", "/static/"])
def test_nothing_but_the_three_files_is_served_as_static(client: Any, path: str) -> None:
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
@pytest.mark.parametrize("url", ["/", "/api/runs/current/events", "/static/app.js", "/api/runs/current/stream"])
def test_every_write_method_is_refused(client: Any, method: str, url: str) -> None:
    assert getattr(client, method)(url).status_code == 405


def test_the_events_endpoint_pages_by_cursor(client: Any) -> None:
    first = client.get("/api/runs/current/events?limit=2").json()
    assert [i["seq"] for i in first["items"]] == [1, 2] and first["more"] is True and first["next_seq"] == 2
    second = client.get("/api/runs/run1/events?after=2&limit=2").json()
    assert [i["seq"] for i in second["items"]] == [3] and second["status"] == "DONE"


def test_bad_query_values_are_a_400_and_an_unknown_run_is_empty_not_a_crash(client: Any) -> None:
    assert client.get("/api/runs/current/events?after=abc").status_code == 400
    page = client.get("/api/runs/nope/events").json()
    assert page["items"] == [] and page["status"] == "UNKNOWN"


def test_the_stream_sends_server_sent_events(client: Any) -> None:
    response = client.get("/api/runs/current/stream?once=1")
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
    assert "event: page" in response.text and "id: 3" in response.text
    data = json.loads(response.text.split("data: ", 1)[1].split("\n\n", 1)[0])
    assert [i["seq"] for i in data["items"]] == [1, 2, 3]


def test_details_serve_the_blob_text_and_reject_other_references(client: Any) -> None:
    ok = client.get(f"/api/details/{client.ref}")
    assert ok.status_code == 200 and ok.json()["text"] == "the test log"
    assert client.get("/api/details/..%2F..%2Fsecret").status_code == 404
    assert client.get("/api/details/sha256:" + "0" * 64).status_code == 404


def test_without_a_project_the_api_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("starlette")
    from starlette.testclient import TestClient

    monkeypatch.chdir(tmp_path)
    response = TestClient(create_app(None)).get("/api/runs/current/events")
    assert response.status_code == 404 and "factory init" in response.json()["error"]


def test_the_page_never_uses_innerhtml_or_external_scripts() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "asf" / "web" / "static"
    script = (root / "app.js").read_text(encoding="utf-8").split("*/", 1)[1]  # skip the header comment
    page = (root / "index.html").read_text(encoding="utf-8").split("-->", 1)[1]
    assert "innerHTML" not in script and "eval(" not in script and "onclick" not in page
    assert "http://" not in page and "https://" not in page and "<form" not in page
