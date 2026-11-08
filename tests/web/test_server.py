# FILE: tests/web/test_server.py
# ROLE: Tests that prove src/asf/web/server.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02; IF-18; D-14b; D-14b-S; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/web/server.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/web/server.py: check_bind_host, create_app, serve, ALLOWED_BIND_HOST, ROUTE_PATHS (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
#   - imports from src/asf/contracts/errors.py: PolicyDenied (expected refusal)
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


def test_loopback_bind_is_accepted() -> None:
    check_bind_host("127.0.0.1")


def test_no_write_routes_exist() -> None:
    pytest.importorskip("starlette")
    app = create_app(None)
    for route in app.routes:
        methods = set(getattr(route, "methods", None) or set())
        assert not (methods & WRITE_METHODS), f"write method on {getattr(route, 'path', route)}"
        assert type(route).__name__ != "WebSocketRoute"
