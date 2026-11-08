# FILE: tests/web/test_narrative.py
# ROLE: Tests that prove src/asf/web/narrative.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02 Active Group Chat; p15 EventEnvelope; IF-18; D-14b narrative amendment; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/web/narrative.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/web/narrative.py: NarrativeItem, Handoff, build_narrative, derive_handoffs (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/web/test_narrative.py` on Windows and Linux once src/asf/web/narrative.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/web/test_narrative.py` and `uv run mypy tests/web/test_narrative.py` are clean.


from asf.web.narrative import Handoff, NarrativeItem, build_narrative, derive_handoffs  # noqa: F401


def test_narrative_item_meets_contract() -> None:
    """Prove NarrativeItem behaves as declared in src/asf/web/narrative.py."""
    raise NotImplementedError("write this test before implementing NarrativeItem")

def test_handoff_meets_contract() -> None:
    """Prove Handoff behaves as declared in src/asf/web/narrative.py."""
    raise NotImplementedError("write this test before implementing Handoff")

def test_build_narrative_meets_contract() -> None:
    """Prove build_narrative behaves as declared in src/asf/web/narrative.py."""
    raise NotImplementedError("write this test before implementing build_narrative")

def test_derive_handoffs_meets_contract() -> None:
    """Prove derive_handoffs behaves as declared in src/asf/web/narrative.py."""
    raise NotImplementedError("write this test before implementing derive_handoffs")
