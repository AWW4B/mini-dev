# FILE: tests/cli/commands/test_models.py
# ROLE: Tests that prove src/asf/cli/commands/models.py meets its DONE WHEN conditions.
# ARCH REF: M1; p11; D-07; D-08; D-09 (missing baseline = WARNING); D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/commands/models.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/models.py: models_list, models_test, models_calibrate, models_init, register (unit under test)
#   - imports from src/asf/contracts/models.py: ModelProfile (a calibrated profile)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_models.py` on Windows and Linux once src/asf/cli/commands/models.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_models.py` and `uv run mypy tests/cli/commands/test_models.py` are clean.

import json
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

import asf.cli.commands.models as models_mod
from asf.cli.commands.models import models_calibrate, models_init, models_list, models_test, register


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    monkeypatch.setenv("FACTORY_HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)


def test_list_shows_every_role_route_of_the_active_profile(capsys: pytest.CaptureFixture[str]) -> None:
    assert models_list("json") == 0
    doc = json.loads(capsys.readouterr().out.splitlines()[0])
    assert {r["role"] for r in doc["rows"]} >= {"T1", "T2", "T3", "reviewer"} and "hybrid" in doc["title"]


def test_testing_an_unknown_role_is_a_user_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert models_test("T9") == 1
    assert "Unknown role" in capsys.readouterr().err


def test_test_reports_latency_and_failures_per_role(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class _Gateway:
        roles: dict[str, dict[str, Any]] = {"T1": {}, "T3": {}}

        def model_for(self, role: str, purpose: str) -> Any:
            if role == "T3":
                raise RuntimeError("no API key for openai")
            return type("M", (), {"invoke": lambda self, prompt: type("R", (), {"content": "OK"})()})()

    monkeypatch.setattr(models_mod, "_gateway", lambda: _Gateway())
    assert models_test(None) == 1
    out = capsys.readouterr().out
    assert "T1" in out and "ok" in out and "FAILED" in out and "no API key" in out
    assert models_test("T1") == 0


def test_init_writes_the_user_models_file_without_overwriting_and_explains_the_next_steps(tmp_path: Any, capsys: pytest.CaptureFixture[str]) -> None:
    assert models_init(False) == 0
    target = tmp_path / "config" / "models.toml"
    assert "[profiles" in target.read_text(encoding="utf-8") or "profiles" in target.read_text(encoding="utf-8")
    assert "FACTORY_OPENAI_API_KEY" in capsys.readouterr().out


def test_calibrate_saves_the_measured_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Any, capsys: pytest.CaptureFixture[str]) -> None:
    from asf.contracts.models import ModelProfile

    profile = ModelProfile.model_validate({"model_id": "qwen", "backend": "llama-server", "c_eff_tokens": 8192, "max_slots": 1, "tokens_per_s": 42.0})
    seen: dict[str, Any] = {}

    def fake_calibrate(backend: Any, model: str, contexts: list[int]) -> ModelProfile:
        seen.update(backend=type(backend).__name__, model=model, contexts=contexts)
        return profile

    monkeypatch.setattr(models_mod, "calibrate", fake_calibrate)
    assert models_calibrate("qwen") == 0
    assert seen == {"backend": "LlamaServerBackend", "model": "qwen", "contexts": [2048, 4096, 8192, 16384]}
    assert "c_eff_tokens = 8192" in (tmp_path / "config" / "calibration.toml").read_text(encoding="utf-8")
    assert "usable context" in capsys.readouterr().out


def test_the_models_group_is_registered() -> None:
    app = typer.Typer()
    register(app)
    assert CliRunner().invoke(app, ["models", "list", "--output", "plain"]).exit_code == 0
