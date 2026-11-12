# FILE: tests/cli/commands/test_skills.py
# ROLE: Tests that prove src/asf/cli/commands/skills.py meets its DONE WHEN conditions.
# ARCH REF: M1; p12; D-17; IF-23; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/commands/skills.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/skills.py: skills_list, skills_validate, register (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_skills.py` on Windows and Linux once src/asf/cli/commands/skills.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_skills.py` and `uv run mypy tests/cli/commands/test_skills.py` are clean.

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from asf.cli.commands.skills import register, skills_list, skills_validate


def test_list_shows_the_project_skills(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("FACTORY_HOME", str(tmp_path))
    assert skills_list("json") == 0
    names = [row["name"] for row in json.loads(capsys.readouterr().out)["rows"]]
    assert {"split-proposal", "write-tests-from-acceptance", "request-structuring"} <= set(names)


def test_validate_reports_problems_as_a_user_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("FACTORY_HOME", str(tmp_path))
    code = skills_validate()
    out = capsys.readouterr()
    assert code in (0, 1) and (("valid" in out.out) if code == 0 else ("Skill" in out.err))


def test_the_skills_group_is_registered() -> None:
    app = typer.Typer()
    register(app)
    assert CliRunner().invoke(app, ["skills", "--help"]).exit_code == 0
