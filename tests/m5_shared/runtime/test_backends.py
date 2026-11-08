# FILE: tests/m5_shared/runtime/test_backends.py
# ROLE: Tests that prove src/asf/m5_shared/runtime/backends.py meets its DONE WHEN conditions.
# ARCH REF: M5; p11; D-08; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/runtime/backends.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/runtime/backends.py: LocalRuntimeBackend, LlamaServerBackend, OllamaBackend, ExternalBackend (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/runtime/test_backends.py` on Windows and Linux once src/asf/m5_shared/runtime/backends.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/runtime/test_backends.py` and `uv run mypy tests/m5_shared/runtime/test_backends.py` are clean.


from pathlib import Path
from typing import Any

import pytest

from asf.m5_shared.runtime.backends import ExternalBackend, LlamaServerBackend, LocalRuntimeBackend, OllamaBackend


class FakeResponse:
    def __init__(self, status_code: int = 200, json_data: Any = None) -> None:
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self) -> Any:
        return self._json_data


def test_local_runtime_backend_meets_contract() -> None:
    """Prove LocalRuntimeBackend behaves as declared in src/asf/m5_shared/runtime/backends.py."""
    llama = LlamaServerBackend()
    ollama = OllamaBackend()
    external = ExternalBackend()

    assert isinstance(llama, LocalRuntimeBackend)
    assert isinstance(ollama, LocalRuntimeBackend)
    assert isinstance(external, LocalRuntimeBackend)


def test_llama_server_backend_meets_contract(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Prove LlamaServerBackend behaves as declared in src/asf/m5_shared/runtime/backends.py."""
    detached_argv: list[str] = []
    killed_pids: list[int] = []

    class FakePlatform:
        @staticmethod
        def detach(argv: list[str], log_path: Path) -> int:
            detached_argv.extend(argv)
            return 4242

        @staticmethod
        def kill_tree(pid: int) -> None:
            killed_pids.append(pid)

    monkeypatch.setattr("asf.m5_shared.runtime.backends.get_platform", lambda: FakePlatform())

    backend = LlamaServerBackend(binary="fake-llama", host="127.0.0.1", port=9090, models_dir=tmp_path)
    base_url = backend.start("qwen.gguf", ctx_tokens=4096, slots=2)
    assert base_url == "http://127.0.0.1:9090/v1"
    assert "fake-llama" in detached_argv[0]
    assert "-c" in detached_argv
    assert "4096" in detached_argv
    assert "-np" in detached_argv
    assert "2" in detached_argv
    assert backend._pid == 4242

    # Stop terminates the process
    backend.stop()
    assert killed_pids == [4242]
    assert backend._pid is None

    # Health check
    class FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def get(self, url: str) -> FakeResponse:
            return FakeResponse(200)

    monkeypatch.setattr("asf.m5_shared.runtime.backends.httpx.Client", FakeClient)
    assert backend.healthy() is True


def test_ollama_backend_meets_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prove OllamaBackend behaves as declared in src/asf/m5_shared/runtime/backends.py."""
    backend = OllamaBackend(base_url="http://127.0.0.1:11434")
    assert backend.name == "ollama"
    url = backend.start("llama3", ctx_tokens=2048, slots=1)
    assert url == "http://127.0.0.1:11434/v1"
    backend.stop()  # no-op

    # Healthy
    class FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def get(self, url: str) -> FakeResponse:
            return FakeResponse(200)

    monkeypatch.setattr("asf.m5_shared.runtime.backends.httpx.Client", FakeClient)
    assert backend.healthy() is True


def test_external_backend_meets_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prove ExternalBackend behaves as declared in src/asf/m5_shared/runtime/backends.py."""
    backend = ExternalBackend(base_url="http://127.0.0.1:8000/v1")
    assert backend.name == "external"
    url = backend.start("custom-model", ctx_tokens=2048, slots=1)
    assert url == "http://127.0.0.1:8000/v1"
    backend.stop()  # no-op

    class FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def get(self, url: str) -> FakeResponse:
            return FakeResponse(200)

    monkeypatch.setattr("asf.m5_shared.runtime.backends.httpx.Client", FakeClient)
    assert backend.healthy() is True
