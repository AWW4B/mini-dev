# FILE: src/asf/m3_orchestration/planning/test_authoring.py
# ROLE: Writes leaf acceptance tests with the planner tier (T3) only, or local drafts gated by user approval when T3 is unavailable.
# ARCH REF: M3; p05; A-4; D-10
# OWNS: Acceptance-test authoring
# DOES NOT OWN: Running tests (M4 verification)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (IF-12 model calls)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (IF-03 decisions)
#   - imports from src/asf/m5_shared/tools/skills.py: SkillsRegistry (IF-23 skills)
#   - imports from src/asf/contracts/tasks.py: TaskNode (leaf)
#   - called by src/asf/m3_orchestration/decomposition/leaf_certifier.py: author_acceptance_tests
#   - called by tests/m3_orchestration/planning/test_test_authoring.py: author_acceptance_tests
#   - emits/consumes: raises DecisionRequest kind APPROVE_LOCAL_TESTS when the per-run switch is on and T3 is unavailable
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Request role T3 with purpose "acceptance_tests"; never T1 (A-4).
#   6. Use the write-tests-from-acceptance skill.
#   7. Use these Agent Skills (load via SkillsRegistry): skills/write-tests-from-acceptance/SKILL.md.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/planning/test_test_authoring.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/planning/test_authoring.py` and `uv run mypy src/asf/m3_orchestration/planning/test_authoring.py` are clean.

from asf.contracts.tasks import TaskNode


def author_acceptance_tests(node: TaskNode, allow_local_with_approval: bool) -> list[str]:
    """Return written test file paths (relative, POSIX style)."""
    raise NotImplementedError
