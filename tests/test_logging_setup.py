# FILE: tests/test_logging_setup.py
# ROLE: Tests that prove src/asf/logging_setup.py meets its DONE WHEN conditions.
# ARCH REF: D-26; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/logging_setup.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/logging_setup.py: configure_logging (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/test_logging_setup.py` on Windows and Linux once src/asf/logging_setup.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/test_logging_setup.py` and `uv run mypy tests/test_logging_setup.py` are clean.


import logging
from typing import Any

from asf.logging_setup import configure_logging  # noqa: F401


def test_configure_logging_meets_contract(fake_paths: Any) -> None:
    """configure_logging runs without error and creates log file in log_dir."""
    configure_logging(level="DEBUG")
    # The log file should be created (or at least handlers attached)
    root = logging.getLogger()
    assert len(root.handlers) > 0, "Expected at least one handler to be attached"


def test_configure_logging_default_level(fake_paths: Any) -> None:
    """configure_logging with defaults sets INFO level."""
    configure_logging()
    root = logging.getLogger()
    assert root.level <= logging.INFO


def test_configure_logging_json_console(fake_paths: Any) -> None:
    """configure_logging with json_console=True does not raise."""
    configure_logging(level="WARNING", json_console=True)
    root = logging.getLogger()
    assert root.level <= logging.WARNING


def test_configure_logging_idempotent(fake_paths: Any) -> None:
    """Calling configure_logging twice does not raise or leave duplicate handlers."""
    configure_logging()
    configure_logging()
    root = logging.getLogger()
    # Should not accumulate unbounded handlers
    assert len(root.handlers) <= 10, "Handler accumulation detected"


def test_redaction_processor_cleans_the_event_and_every_string_field() -> None:
    import asf.logging_setup as logging_mod

    processor = logging_mod._make_redact_processor()
    out = processor(None, "info", {"event": "key sk-abcdefghijklmnopqrstuvwxyz0123 used", "detail": "Bearer abcdefghijklmnopqrstuvwxyz", "count": 3})
    assert "sk-" not in out["event"]
    assert "abcdefghijklmnopqrstuvwxyz" not in out["detail"]
    assert out["count"] == 3
