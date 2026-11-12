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
#   - imports from src/asf/contracts/contract_spec.py: ContractStatus (promote contracts to VERIFIED)
#   - imports from src/asf/contracts/workspace.py: WorkspaceOp (merge / revert)
#   - imports from src/asf/platform/base.py: ProcessResult, SandboxSpec (sandboxed gate commands)
#   - called by src/asf/m4_execution/worker/worker_graph.py: verify_change_set
#   - called by tests/m4_execution/verification/test_gate.py: verify_change_set, scan_diff
#   - called by src/asf/m3_orchestration/run_graph.py: verify_change_set, run_in_sandbox
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

import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from asf.contracts.contract_spec import ContractStatus
from asf.contracts.outcomes import ChangeSet, FailureClass, Requeue, TaskOutcome
from asf.contracts.workspace import WorkspaceOp
from asf.m4_execution.verification.failure_classifier import classify_failure
from asf.m4_execution.verification.reviewer import review_change
from asf.m4_execution.verification.test_selection import select_tests
from asf.m5_shared.registry.registry import ContractRegistry
from asf.m5_shared.workspace.workspace import Workspace
from asf.platform.base import ProcessResult, SandboxSpec
from asf.platform.select import get_platform

logger = logging.getLogger(__name__)

GATE_TIMEOUT_S = 300
Runner = Callable[[list[str], Path, int], ProcessResult]
Emit = Callable[[str, dict[str, Any]], None]

_ADDED_SECRET = re.compile(r"^\+.*(-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{20,}|\bAKIA[0-9A-Z]{16}\b|\bgsk_[A-Za-z0-9]{20,})")
_WEAKENING_ADDED = re.compile(r"^\+\s*(@pytest\.mark\.(skip|xfail)|@unittest\.skip|pytest\.skip\(|.*\.skip\()")
_ASSERT_LINE = re.compile(r"^[+-]\s*(assert\b|self\.assert\w+\()")


def _is_test_path(path: str) -> bool:
    p = Path(path)
    return p.name.startswith("test_") or "tests" in p.parts


def scan_diff(diff_text: str) -> list[str]:
    """Policy problems visible in a unified diff: secrets added, tests weakened (fewer asserts, skips added)."""
    problems: list[str] = []
    current = ""
    removed_asserts: dict[str, int] = {}
    added_asserts: dict[str, int] = {}
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            continue
        if line.startswith(("+++", "---")):
            continue
        if _ADDED_SECRET.match(line):
            problems.append(f"a secret-looking value was added in {current or 'the diff'}")
        if current and _is_test_path(current):
            if _WEAKENING_ADDED.match(line):
                problems.append(f"a skip/xfail was added to {current}")
            match = _ASSERT_LINE.match(line)
            if match:
                bucket = removed_asserts if line.startswith("-") else added_asserts
                bucket[current] = bucket.get(current, 0) + 1
    for path, removed in removed_asserts.items():
        if removed > added_asserts.get(path, 0):
            problems.append(f"assertions were removed from {path} ({removed} removed, {added_asserts.get(path, 0)} added)")
    return list(dict.fromkeys(problems))


def _sandbox_runner(argv: list[str], cwd: Path, timeout_s: int) -> ProcessResult:
    """Run a gate command in the best sandbox; tier C (no usable sandbox) refuses to run project code."""
    backend = get_platform().sandbox()
    tier = getattr(backend.tier, "value", backend.tier)
    if tier not in ("A", "B") or not backend.available():
        return ProcessResult(exit_code=126, stdout=b"", stderr=b"sandbox unavailable: no tier A or B sandbox", timed_out=False, duration_ms=0)
    spec = SandboxSpec(argv=argv, cwd=cwd, writable_paths=[cwd], readable_paths=[cwd], network=False, timeout_s=timeout_s)
    try:
        return backend.run(spec)
    except OSError as err:
        return ProcessResult(exit_code=127, stdout=b"", stderr=f"command not found or not runnable: {err}".encode(), timed_out=False, duration_ms=0)


run_in_sandbox = _sandbox_runner  # public name: the integration tests run through the same sandbox


def _log_of(result: ProcessResult) -> str:
    text = (result.stdout + b"\n" + result.stderr).decode("utf-8", errors="replace")
    return ("[timed out]\n" if result.timed_out else "") + text


def verify_change_set(
    change: ChangeSet,
    *,
    workspace: Workspace | None = None,
    registry: ContractRegistry | None = None,
    gateway: Any = None,
    allowed_files: list[str] | None = None,
    acceptance_refs: list[str] | None = None,
    contract_ids: list[str] | None = None,
    capsule_lines: list[str] | None = None,
    risky: bool = False,
    runner: Runner | None = None,
    emit: Emit | None = None,
) -> Requeue | TaskOutcome | None:
    """None = verified and merged; Requeue = LOCAL_BUG; TaskOutcome = other classes.

    Optional collaborators: ``workspace`` (default: the repository above the task worktree), ``registry`` (contracts
    promoted to VERIFIED on success), ``gateway`` (T1 classifier and reviewer), ``runner`` (gate command runner, default
    the sandbox), ``emit`` (receives GATE_RESULT-shaped payloads, one per gate).
    """
    worktree = Path(change.worktree_path)
    ws = workspace if workspace is not None else Workspace(worktree.parents[1])
    run: Runner = runner if runner is not None else _sandbox_runner
    task_id = str(change.task_id)

    def publish(gate: str, passed: bool, summary: str, evidence: str | None = None) -> None:
        if emit is not None:
            emit("GATE_RESULT", {"gate": gate, "passed": passed, "summary": summary, "evidence_ref": evidence})

    def evidence_for(text: str) -> str:
        return ws.blobs.put(text.encode("utf-8"))

    def requeue(failure_class: FailureClass, text: str) -> Requeue:
        return Requeue.model_validate({"task_id": task_id, "failure_class": failure_class, "evidence_ref": evidence_for(text)})

    def outcome(failure_class: FailureClass, text: str) -> TaskOutcome:
        return TaskOutcome.model_validate(
            {"task_id": task_id, "failure_class": failure_class, "evidence_ref": evidence_for(text), "attempts": change.attempt_no}
        )

    def revert() -> None:
        result = ws.apply(WorkspaceOp.model_validate({"kind": "revert", "task_id": task_id}))
        if not result.ok:
            logger.error("could not revert the worktree of task %s: %s", task_id, result.error_kind)

    # 1. Scope check: allowed files only, no deleted or weakened tests, no secrets in the diff.
    violations: list[str] = []
    if allowed_files is not None:
        allowed = {Path(p).as_posix() for p in allowed_files}
        violations += [f"{p} is outside the allowed files" for p in (Path(f).as_posix() for f in change.files_touched) if p not in allowed]
    violations += [f"test {p} was deleted" for p in change.files_touched if _is_test_path(p) and not (worktree / p).exists()]
    try:
        diff_text = ws.blobs.get(change.diff_ref).decode("utf-8", errors="replace")
    except FileNotFoundError:
        diff_text = ""
        violations.append(f"the diff {change.diff_ref} is missing, so the change cannot be checked")
    violations += scan_diff(diff_text)
    if violations:
        text = "Policy violation:\n- " + "\n- ".join(violations)
        publish("scope", False, "; ".join(violations))
        revert()
        return requeue(FailureClass.POLICY_VIOLATION, text)
    publish("scope", True, "scope ok")

    # 2. Static gates, then the selected tests, inside the sandbox.
    python_files = [p for p in change.files_touched if p.endswith(".py")]
    commands: list[tuple[str, list[str]]] = []
    if python_files:
        commands.append(("lint", ["uv", "run", "ruff", "check", *python_files]))
        commands.append(("types", ["uv", "run", "mypy", *python_files]))
    selected = select_tests(change, acceptance_refs or [])
    if selected:
        commands.append(("tests", ["uv", "run", "pytest", "-q", "--no-header", *selected]))

    for gate, argv in commands:
        result = run(argv, worktree, GATE_TIMEOUT_S)
        log = _log_of(result)
        if result.exit_code == 0 and not result.timed_out:
            publish(gate, True, f"{gate} passed")
            continue
        failure_class = classify_failure(log, gateway=gateway)
        if failure_class is FailureClass.FLAKY:
            again = run(argv, worktree, GATE_TIMEOUT_S)
            if again.exit_code == 0 and not again.timed_out:
                publish(gate, True, f"{gate} passed on the rerun (flaky)")
                continue
            failure_class = FailureClass.LOCAL_BUG  # it failed twice: treat it as real
            log += "\n--- rerun ---\n" + _log_of(again)
        publish(gate, False, f"{gate} failed ({failure_class.value})", evidence_for(log))
        if failure_class in (FailureClass.LOCAL_BUG, FailureClass.POLICY_VIOLATION):
            return requeue(FailureClass.LOCAL_BUG, log)
        return outcome(failure_class, log)

    # 3. Reviewer for risky changes (advisory, but blocking findings send the change back).
    if risky and gateway is not None:
        findings = review_change(change, capsule_lines or [], gateway=gateway, diff_text=diff_text)
        if findings:
            text = "Reviewer findings:\n- " + "\n- ".join(findings)
            publish("review", False, f"{len(findings)} blocking finding(s)")
            return requeue(FailureClass.LOCAL_BUG, text)
        publish("review", True, "no blocking findings")

    # 4. Merge the task branch into the parent integration branch.
    merged = ws.apply(WorkspaceOp.model_validate({"kind": "merge", "task_id": task_id, "branch": f"task/{task_id}"}))
    if not merged.ok:
        publish("merge", False, str(merged.error_kind))
        return requeue(FailureClass.LOCAL_BUG, f"Merge failed ({merged.error_kind}); the next attempt starts from the new parent commit.")
    publish("merge", True, f"merged at {merged.commit}")

    # 5. Contracts produced by the task become VERIFIED.
    if registry is not None:
        for contract_id in contract_ids or []:
            registry.promote(contract_id, ContractStatus.VERIFIED)
    return None
