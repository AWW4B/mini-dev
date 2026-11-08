# FILE: tests/m3_orchestration/decomposition/test_rubric.py
# ROLE: Tests that prove src/asf/m3_orchestration/decomposition/rubric.py meets its DONE WHEN conditions.
# ARCH REF: M3; p05 T1 rubric; D-09 tiny-model tasks; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/decomposition/rubric.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/decomposition/rubric.py: RubricScore, score_node (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/decomposition/test_rubric.py` on Windows and Linux once src/asf/m3_orchestration/decomposition/rubric.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/decomposition/test_rubric.py` and `uv run mypy tests/m3_orchestration/decomposition/test_rubric.py` are clean.


from asf.m3_orchestration.decomposition.rubric import RubricScore, score_node  # noqa: F401


def test_rubric_score_meets_contract() -> None:
    """Prove RubricScore behaves as declared in src/asf/m3_orchestration/decomposition/rubric.py."""
    raise NotImplementedError("write this test before implementing RubricScore")

def test_score_node_meets_contract() -> None:
    """Prove score_node behaves as declared in src/asf/m3_orchestration/decomposition/rubric.py."""
    raise NotImplementedError("write this test before implementing score_node")
