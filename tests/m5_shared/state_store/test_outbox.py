# FILE: tests/m5_shared/state_store/test_outbox.py
# ROLE: Tests that prove src/asf/m5_shared/state_store/outbox.py meets its DONE WHEN conditions.
# ARCH REF: M5; p09 outbox; IF-17; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/state_store/outbox.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/state_store/outbox.py: OutboxRelay (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/state_store/test_outbox.py` on Windows and Linux once src/asf/m5_shared/state_store/outbox.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/state_store/test_outbox.py` and `uv run mypy tests/m5_shared/state_store/test_outbox.py` are clean.


from asf.m5_shared.state_store.outbox import OutboxRelay  # noqa: F401


def test_outbox_relay_meets_contract() -> None:
    """Prove OutboxRelay behaves as declared in src/asf/m5_shared/state_store/outbox.py."""
    raise NotImplementedError("write this test before implementing OutboxRelay")
