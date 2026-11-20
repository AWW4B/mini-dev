# FILE: tests/m3_orchestration/test_autonomy.py
# ROLE: Tests that prove src/asf/m3_orchestration/autonomy.py meets its DONE WHEN conditions.
# ARCH REF: M3; p04 Escalation & Recovery; IF-10; A-3; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/autonomy.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/autonomy.py: choose_by_policy (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/test_autonomy.py` on Windows and Linux once src/asf/m3_orchestration/autonomy.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/test_autonomy.py` and `uv run mypy tests/m3_orchestration/test_autonomy.py` are clean.

from asf.m3_orchestration.autonomy import choose_by_policy


def test_the_policy_approves_accepts_and_replans_once_then_abandons() -> None:
    assert choose_by_policy(["approve", "reject"], 0)[0] == "approve"
    assert choose_by_policy(["accept_larger_leaf", "abandon_subtree"], 0)[0] == "accept_larger_leaf"
    assert choose_by_policy(["replan", "abandon_subtree", "abort_run"], 0)[0] == "replan"
    choice, reason = choose_by_policy(["replan", "abandon_subtree", "abort_run"], 1)
    assert choice == "abandon_subtree" and "abandoned and reported" in reason


def test_the_policy_never_aborts_the_run_on_its_own() -> None:
    assert choose_by_policy(["abort_run"], 0)[0] == "abort_run"  # only option left: it is taken and recorded, never preferred
    assert choose_by_policy(["abort_run", "abandon_subtree"], 5)[0] == "abandon_subtree"
