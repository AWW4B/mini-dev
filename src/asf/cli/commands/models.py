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

import typer


def models_list(output: str = "rich") -> int:
    raise NotImplementedError


def models_test(role: str | None) -> int:
    raise NotImplementedError


def models_calibrate(model: str) -> int:
    raise NotImplementedError


def models_init(interactive: bool = True) -> int:
    raise NotImplementedError


def register(app: typer.Typer) -> None:
    """Attach the `models` command(s) to the root Typer app."""
    raise NotImplementedError
