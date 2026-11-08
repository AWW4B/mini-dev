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


from asf.cli.commands.skills import register, skills_list, skills_validate  # noqa: F401


def test_skills_list_meets_contract() -> None:
    """Prove skills_list behaves as declared in src/asf/cli/commands/skills.py."""
    raise NotImplementedError("write this test before implementing skills_list")

def test_skills_validate_meets_contract() -> None:
    """Prove skills_validate behaves as declared in src/asf/cli/commands/skills.py."""
    raise NotImplementedError("write this test before implementing skills_validate")

def test_register_meets_contract() -> None:
    """Prove register behaves as declared in src/asf/cli/commands/skills.py."""
    raise NotImplementedError("write this test before implementing register")
