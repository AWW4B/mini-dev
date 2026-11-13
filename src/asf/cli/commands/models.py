# FILE: src/asf/cli/commands/models.py
# ROLE: Implements `factory models list|test|calibrate|init`.
# ARCH REF: M1; p11; D-07; D-08; D-09 (missing baseline = WARNING)
# OWNS: Argument parsing and output for this command group
# DOES NOT OWN: Business logic (lives in the imported modules)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (routes)
#   - imports from src/asf/m5_shared/runtime/calibration.py: calibrate (calibration)
#   - imports from src/asf/m5_shared/runtime/backends.py: LlamaServerBackend, OllamaBackend, ExternalBackend (backends)
#   - imports from src/asf/config/loader.py: write_user_toml (models init)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: EXIT_OK, EXIT_USER, guard, project_root, renderer_for (shared CLI plumbing)
#   - imports from src/asf/config/settings.py: load_settings (the active profile)
#   - imports from src/asf/contracts/budget.py: RunBudget (a tiny budget for connectivity tests)
#   - called by src/asf/cli/flows.py: models_init
#   - called by src/asf/cli/app.py: register
#   - called by tests/cli/commands/test_models.py: models_list, models_test, models_calibrate, models_init, register
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
# DONE WHEN: (1) tests/cli/commands/test_models.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/commands/models.py` and `uv run mypy src/asf/cli/commands/models.py` are clean.

import time
from typing import TYPE_CHECKING, Any

import typer

from asf.cli.context import EXIT_OK, EXIT_USER, guard, project_root, renderer_for
from asf.config.loader import load_layered, write_user_toml
from asf.config.settings import load_settings
from asf.contracts.budget import RunBudget
from asf.m5_shared.runtime.backends import ExternalBackend, LlamaServerBackend, OllamaBackend
from asf.m5_shared.runtime.calibration import calibrate

if TYPE_CHECKING:
    from asf.m5_shared.gateway.gateway import ModelGateway

CALIBRATION_CONTEXTS = [2048, 4096, 8192, 16384]
_PING = "Reply with the single word OK."


def _gateway() -> "ModelGateway":
    from asf.m5_shared.gateway.gateway import ModelGateway

    profile = load_settings(project_root()).profile
    budget = RunBudget.model_validate(
        {"run_id": "models", "max_remote_tokens": 10_000, "max_local_tokens": 10_000, "max_api_spend": 1.0, "max_wall_clock_s": 600, "max_task_nodes": 1}
    )
    return ModelGateway(profile, budget)


def models_list(output: str = "rich") -> int:
    gateway = _gateway()
    renderer = renderer_for(output)
    rows = [
        [role, str(cfg.get("provider", "?")), str(cfg.get("model") or "(provider default)"), ", ".join(str(f) for f in cfg.get("fallbacks", [])) or "-", gateway.strategies.get(role, "-")]
        for role, cfg in gateway.roles.items()
    ]
    renderer.table(f"Model routes (profile {gateway.profile_name})", ["role", "provider", "model", "fallbacks", "strategy"], rows)
    for warning in gateway.baseline_warnings():
        renderer.message(warning, "warning")
    return EXIT_OK


def models_test(role: str | None) -> int:
    """Send one tiny request to each route (or just ROLE) and report latency; this is the only command that spends tokens."""
    gateway = _gateway()
    renderer = renderer_for("plain")
    roles = [role] if role else list(gateway.roles)
    unknown = [r for r in roles if r not in gateway.roles]
    if unknown:
        renderer.message(f"Unknown role(s): {', '.join(unknown)}. Known roles: {', '.join(gateway.roles)}.", "error")
        return EXIT_USER
    rows: list[list[Any]] = []
    failed = 0
    for name in roles:
        started = time.monotonic()
        try:
            reply = gateway.model_for(name, purpose="connectivity_test").invoke(_PING)  # type: ignore[arg-type]
            text = str(getattr(reply, "content", reply)).strip().replace("\n", " ")[:40]
            rows.append([name, "ok", f"{(time.monotonic() - started) * 1000:.0f} ms", text])
        except Exception as err:  # noqa: BLE001 - provider errors vary; the point of the command is to show them
            failed += 1
            rows.append([name, "FAILED", "-", str(err)[:80]])
    renderer.table("Model connectivity", ["role", "status", "latency", "reply / error"], rows)
    return EXIT_USER if failed else EXIT_OK


def _backend(runtime: dict[str, Any]) -> Any:
    kind = str(runtime.get("backend", "llama-server"))
    base_url = str(runtime.get("base_url") or "")
    if kind == "ollama":
        return OllamaBackend(base_url or "http://127.0.0.1:11434")
    if kind == "external":
        return ExternalBackend(base_url or "http://127.0.0.1:8000/v1")
    return LlamaServerBackend(binary=str(runtime.get("binary") or "") or None)


def models_calibrate(model: str) -> int:
    """Measure a local model's usable context and slots, and keep the ModelProfile in the user's calibration.toml."""
    renderer = renderer_for("plain")
    runtime = load_layered("models").get("runtime", {})
    backend = _backend(runtime)
    profile = calibrate(backend, model, CALIBRATION_CONTEXTS)
    write_user_toml("calibration", {model: profile.model_dump(mode="json")})
    renderer.record(
        f"Calibration of {model}",
        {"backend": profile.backend, "usable context": profile.c_eff_tokens, "slots": profile.max_slots, "tokens/s": profile.tokens_per_s, "saved to": "calibration.toml (user config)"},
    )
    return EXIT_OK


def models_init(interactive: bool = True) -> int:
    """Write the user's models.toml from the packaged defaults (never overwrites) and say what is still needed."""
    renderer = renderer_for("plain")
    data = load_layered("models")
    path = write_user_toml("models", {k: v for k, v in data.items() if k in ("active_profile", "runtime", "profiles", "suggested_local_models")})
    renderer.message(f"Model settings are in {path}.", "success")
    renderer.message(
        "Next: put each provider key in the environment (FACTORY_OPENAI_API_KEY, FACTORY_GROQ_API_KEY, FACTORY_ANTHROPIC_API_KEY, "
        "FACTORY_GEMINI_API_KEY) or the OS keyring, install llama.cpp or Ollama for local models, then run `factory doctor`."
    )
    return EXIT_OK


def register(app: typer.Typer) -> None:
    """Attach the `models` command(s) to the root Typer app."""
    group = typer.Typer(help="Model routes, connectivity and calibration.", no_args_is_help=True)

    @group.command("list")
    def list_cmd(output: str = typer.Option("rich", "--output", "-o")) -> None:
        raise typer.Exit(code=guard(lambda: models_list(output)))

    @group.command("test")
    def test_cmd(role: str | None = typer.Argument(None)) -> None:
        raise typer.Exit(code=guard(lambda: models_test(role)))

    @group.command("calibrate")
    def calibrate_cmd(model: str) -> None:
        raise typer.Exit(code=guard(lambda: models_calibrate(model)))

    @group.command("init")
    def init_cmd(interactive: bool = typer.Option(True, "--interactive/--no-interactive")) -> None:
        raise typer.Exit(code=guard(lambda: models_init(interactive)))

    app.add_typer(group, name="models")
