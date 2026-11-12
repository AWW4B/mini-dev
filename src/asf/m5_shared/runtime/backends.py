# FILE: src/asf/m5_shared/runtime/backends.py
# ROLE: Defines the LocalRuntimeBackend adapter and its three implementations: managed llama-server (default), Ollama, external server.
# ARCH REF: M5; p11; D-08
# OWNS: Starting/stopping/health-checking local inference servers
# DOES NOT OWN: Choosing which model to load (local_runtime.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/platform/select.py: get_platform (platform adapter)
#   - imports from src/asf/config/paths.py: AppPaths, get_paths (cross-platform base directories)
#   - called by src/asf/m5_shared/runtime/local_runtime.py: LocalRuntimeBackend
#   - called by src/asf/m5_shared/runtime/calibration.py: LocalRuntimeBackend
#   - called by src/asf/cli/commands/models.py: LlamaServerBackend, OllamaBackend, ExternalBackend
#   - called by tests/m5_shared/runtime/test_backends.py: LocalRuntimeBackend, LlamaServerBackend, OllamaBackend, ExternalBackend
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Start llama-server with an argument list built from models.toml (model path, ctx, -np slots, --n-cpu-moe, KV cache types, --metrics); the binary path comes from config or shutil.which.
#   9. Health via GET /health; tokenization via POST /tokenize; never assume a model is present.
#   10. Ollama and external backends are reached through their OpenAI-compatible base URL.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/runtime/test_backends.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/runtime/backends.py` and `uv run mypy src/asf/m5_shared/runtime/backends.py` are clean.

import logging
import shutil
from pathlib import Path
from typing import Protocol, runtime_checkable

import httpx

from asf.config.paths import AppPaths, get_paths  # noqa: F401
from asf.platform.select import get_platform

logger = logging.getLogger(__name__)


@runtime_checkable
class LocalRuntimeBackend(Protocol):
    name: str

    def start(self, model_id: str, ctx_tokens: int, slots: int) -> str:
        """Ensure the server serves model_id; return its OpenAI-compatible base URL."""
        ...

    def stop(self) -> None: ...

    def healthy(self) -> bool: ...


class LlamaServerBackend:
    name: str = "llama-server"
    binary: str | None
    host: str
    port: int
    models_dir: Path | None
    _pid: int | None

    def __init__(
        self,
        binary: str | None = None,
        host: str = "127.0.0.1",
        port: int = 8080,
        models_dir: Path | None = None,
    ) -> None:
        self.binary = binary
        self.host = host
        self.port = port
        self.models_dir = models_dir
        self._pid = None

    def start(self, model_id: str, ctx_tokens: int, slots: int) -> str:
        bin_path = self.binary or shutil.which("llama-server") or shutil.which("llama.cpp") or "llama-server"
        mdir = self.models_dir or (get_paths().data_dir / "models")
        model_file = mdir / model_id

        argv = [
            bin_path,
            "-m",
            str(model_file),
            "-c",
            str(ctx_tokens),
            "-np",
            str(slots),
            "--host",
            self.host,
            "--port",
            str(self.port),
            "--metrics",
        ]

        log_path = get_paths().log_dir / "llama-server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        self._pid = get_platform().detach(argv, log_path)
        return f"http://{self.host}:{self.port}/v1"

    def stop(self) -> None:
        if self._pid is not None:
            try:
                get_platform().kill_tree(self._pid)
            except Exception:  # noqa: BLE001 - the platform adapter raises OS-specific errors
                logger.warning("could not stop the llama-server process tree (pid %s)", self._pid, exc_info=True)
            finally:
                self._pid = None

    def healthy(self) -> bool:
        url = f"http://{self.host}:{self.port}/health"
        try:
            with httpx.Client(timeout=1.0) as client:
                resp = client.get(url)
                return resp.status_code == 200
        except httpx.HTTPError:  # not reachable (yet): the caller polls
            return False

    def tokenize(self, content: str) -> list[int]:
        url = f"http://{self.host}:{self.port}/tokenize"
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.post(url, json={"content": content})
                if resp.status_code == 200:
                    data = resp.json()
                    tokens = data.get("tokens", [])
                    return [int(t) for t in tokens]
        except (httpx.HTTPError, ValueError):
            logger.warning("tokenize request to %s failed; the caller falls back to an estimate", url, exc_info=True)
        return []


class OllamaBackend:
    name: str = "ollama"
    base_url: str

    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self.base_url = base_url.rstrip("/")

    def start(self, model_id: str, ctx_tokens: int, slots: int) -> str:
        return f"{self.base_url}/v1"

    def stop(self) -> None:
        pass

    def healthy(self) -> bool:
        try:
            with httpx.Client(timeout=1.0) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except httpx.HTTPError:  # not reachable (yet): the caller polls
            return False


class ExternalBackend:
    name: str = "external"
    base_url: str

    def __init__(self, base_url: str = "http://127.0.0.1:8000/v1") -> None:
        self.base_url = base_url.rstrip("/")

    def start(self, model_id: str, ctx_tokens: int, slots: int) -> str:
        return self.base_url

    def stop(self) -> None:
        pass

    def healthy(self) -> bool:
        try:
            with httpx.Client(timeout=1.0) as client:
                resp = client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except httpx.HTTPError:  # not reachable (yet): the caller polls
            return False
