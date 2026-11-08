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

from typing import Protocol


class LocalRuntimeBackend(Protocol):
    name: str

    def start(self, model_id: str, ctx_tokens: int, slots: int) -> str:
        """Ensure the server serves model_id; return its OpenAI-compatible base URL."""
        ...

    def stop(self) -> None: ...

    def healthy(self) -> bool: ...


class LlamaServerBackend:
    name = "llama-server"

    def start(self, model_id: str, ctx_tokens: int, slots: int) -> str:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def healthy(self) -> bool:
        raise NotImplementedError


class OllamaBackend:
    name = "ollama"

    def start(self, model_id: str, ctx_tokens: int, slots: int) -> str:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def healthy(self) -> bool:
        raise NotImplementedError


class ExternalBackend:
    name = "external"

    def start(self, model_id: str, ctx_tokens: int, slots: int) -> str:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def healthy(self) -> bool:
        raise NotImplementedError
