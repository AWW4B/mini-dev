# FILE: tests/doctor/test_report.py
# ROLE: Tests that prove src/asf/doctor/report.py meets its DONE WHEN conditions.
# ARCH REF: FR-4 doctor report; D-45; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/doctor/report.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/doctor/report.py: write_report, exit_code_for (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/doctor/test_report.py` on Windows and Linux once src/asf/doctor/report.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/doctor/test_report.py` and `uv run mypy tests/doctor/test_report.py` are clean.


import json
from pathlib import Path

from asf.doctor.report import exit_code_for, write_report


class DummyCheckResult:
    def __init__(self, name: str, status: str, detail: str, fix_hints: dict[str, str] | None = None) -> None:
        self.name = name
        self.status = status
        self.detail = detail
        self.fix_hints = fix_hints or {}

    def model_dump(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "fix_hints": self.fix_hints,
        }


def test_write_report_meets_contract(tmp_path: Path) -> None:
    """Prove write_report behaves as declared in src/asf/doctor/report.py."""
    results = [
        DummyCheckResult("python", "ok", "Python 3.14"),
        DummyCheckResult("git", "warn", "git not found", {"apt": "apt install git"}),
    ]
    md_path, json_path = write_report(results, dest_dir=tmp_path)  # type: ignore[arg-type]

    assert md_path.exists()
    assert json_path.exists()
    assert md_path.name.endswith(".md")
    assert json_path.name.endswith(".json")

    # Verify JSON content
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["name"] == "python"
    assert data[1]["status"] == "warn"

    # Verify Markdown content
    md_text = md_path.read_text(encoding="utf-8")
    assert "Doctor Report" in md_text
    assert "python" in md_text
    assert "git" in md_text


def test_exit_code_for_meets_contract() -> None:
    """Prove exit_code_for behaves as declared in src/asf/doctor/report.py."""
    ok_results = [DummyCheckResult("python", "ok", "ok")]
    assert exit_code_for(ok_results) == 0  # type: ignore[arg-type]

    warn_results = [
        DummyCheckResult("python", "ok", "ok"),
        DummyCheckResult("ripgrep", "warn", "missing"),
    ]
    assert exit_code_for(warn_results) == 1  # type: ignore[arg-type]

    fail_results = [
        DummyCheckResult("python", "fail", "wrong version"),
        DummyCheckResult("ripgrep", "warn", "missing"),
    ]
    assert exit_code_for(fail_results) == 2  # type: ignore[arg-type]
