# FILE: tests/cli/commands/test_inbox.py
# ROLE: Tests that prove src/asf/cli/commands/inbox.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02 Decision Inbox; IF-03; IF-04; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/commands/inbox.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/commands/inbox.py: inbox_list, inbox_show, inbox_answer, register (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/commands/test_inbox.py` on Windows and Linux once src/asf/cli/commands/inbox.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/commands/test_inbox.py` and `uv run mypy tests/cli/commands/test_inbox.py` are clean.


from asf.cli.commands.inbox import inbox_answer, inbox_list, inbox_show, register  # noqa: F401


def test_inbox_list_meets_contract() -> None:
    """Prove inbox_list behaves as declared in src/asf/cli/commands/inbox.py."""
    raise NotImplementedError("write this test before implementing inbox_list")

def test_inbox_show_meets_contract() -> None:
    """Prove inbox_show behaves as declared in src/asf/cli/commands/inbox.py."""
    raise NotImplementedError("write this test before implementing inbox_show")

def test_inbox_answer_meets_contract() -> None:
    """Prove inbox_answer behaves as declared in src/asf/cli/commands/inbox.py."""
    raise NotImplementedError("write this test before implementing inbox_answer")

def test_register_meets_contract() -> None:
    """Prove register behaves as declared in src/asf/cli/commands/inbox.py."""
    raise NotImplementedError("write this test before implementing register")
