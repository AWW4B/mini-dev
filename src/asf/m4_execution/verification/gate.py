# FILE: src/asf/m4_execution/verification/gate.py
# ROLE: Verification Gate: scope check, static gates (ruff, mypy), sandboxed tests, classification, review, merge, TaskVerified.
# ARCH REF: M4; p08 Verification Gate; IF-21; IF-10; IF-07 implemented signatures; D-33; D-34
# OWNS: Gate pipeline per attempt
# DOES NOT OWN: Bottom-up integration
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/outcomes.py: ChangeSet, Requeue, TaskOutcome (IF-21/IF-10)
#   - imports from src/asf/m4_execution/verification/test_selection.py: select_tests (selection)
#   - imports from src/asf/m4_execution/verification/failure_classifier.py: classify_failure (classes)
#   - imports from src/asf/m4_execution/verification/reviewer.py: review_change (review)
#   - imports from src/asf/m5_shared/workspace/workspace.py: Workspace (IF-15 git operations)
#   - imports from src/asf/m5_shared/registry/registry.py: ContractRegistry (IF-07/IF-08)
#   - imports from src/asf/platform/select.py: get_platform (platform adapter)
#   - called by src/asf/m4_execution/worker/worker_graph.py: verify_change_set
#   - called by tests/m4_execution/verification/test_gate.py: verify_change_set
#   - emits/consumes: emits GATE_RESULT (gate, passed, summary, evidence_ref) per gate, HANDOFF_SENT (gate -> scheduler on requeue), STATE_CHANGED VERIFIED
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Run gates inside the per-project uv gate venv in the sandbox (D-34); tier C suspends at the gate.
#   9. Reject deleted or weakened tests as POLICY_VIOLATION.
#   10. Rerun FLAKY once; ENV/INFRA retries at most 3 then HITL.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m4_execution/verification/test_gate.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m4_execution/verification/gate.py` and `uv run mypy src/asf/m4_execution/verification/gate.py` are clean.

from asf.contracts.outcomes import ChangeSet, Requeue, TaskOutcome


def verify_change_set(change: ChangeSet) -> Requeue | TaskOutcome | None:
    """None = verified and merged; Requeue = LOCAL_BUG; TaskOutcome = other classes."""
    raise NotImplementedError
