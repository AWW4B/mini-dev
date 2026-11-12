# FILE: tests/m4_execution/verification/test_gate.py
# ROLE: Tests that prove src/asf/m4_execution/verification/gate.py meets its DONE WHEN conditions.
# ARCH REF: M4; p08 Verification Gate; IF-21; IF-10; IF-07 implemented signatures; D-33; D-34; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m4_execution/verification/gate.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m4_execution/verification/gate.py: verify_change_set, scan_diff (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m4_execution/verification/test_gate.py` on Windows and Linux once src/asf/m4_execution/verification/gate.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m4_execution/verification/test_gate.py` and `uv run mypy tests/m4_execution/verification/test_gate.py` are clean.

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from asf.m4_execution.verification.gate import scan_diff, verify_change_set


class _Blobs:
    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    def put(self, data: bytes) -> str:
        ref = "sha256:" + hashlib.sha256(data).hexdigest()
        self.data[ref] = data
        return ref

    def get(self, ref: str) -> bytes:
        if ref not in self.data:
            raise FileNotFoundError(ref)
        return self.data[ref]


class _Workspace:
    def __init__(self, merge_ok: bool = True) -> None:
        self.blobs = _Blobs()
        self.ops: list[str] = []
        self.merge_ok = merge_ok

    def apply(self, op: Any) -> Any:
        kind = op.kind.value
        self.ops.append(kind)
        if kind == "merge" and not self.merge_ok:
            return SimpleNamespace(ok=False, commit=None, error_kind="merge_conflict")
        return SimpleNamespace(ok=True, commit="abc123", error_kind=None)


class _Registry:
    def __init__(self) -> None:
        self.promoted: list[tuple[str, str]] = []

    def promote(self, contract_id: str, status: Any) -> None:
        self.promoted.append((contract_id, status.value))


def _result(code: int = 0, out: str = "", err: str = "", timed_out: bool = False) -> Any:
    return SimpleNamespace(exit_code=code, stdout=out.encode(), stderr=err.encode(), timed_out=timed_out, duration_ms=1)


class _Runner:
    def __init__(self, *results: Any) -> None:
        self.results = list(results)
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], cwd: Path, timeout_s: int) -> Any:
        self.calls.append(argv)
        return self.results.pop(0) if self.results else _result()


def _setup(tmp_path: Path, *, diff: str = "", files: list[str] | None = None, merge_ok: bool = True) -> tuple[Any, _Workspace]:
    ws = _Workspace(merge_ok=merge_ok)
    worktree = tmp_path / "repo" / ".worktrees" / "t1"
    (worktree / "src").mkdir(parents=True)
    (worktree / "tests").mkdir(parents=True)
    touched = files if files is not None else ["src/billing.py"]
    for rel in touched:
        (worktree / rel).write_text("x = 1\n", encoding="utf-8")
    change = SimpleNamespace(
        task_id="t1", attempt_no=1, diff_ref=ws.blobs.put(diff.encode("utf-8")), worktree_path=str(worktree),
        files_touched=touched, self_report="done",
    )
    return change, ws


def _verify(change: Any, ws: Any, **kwargs: Any) -> Any:
    return verify_change_set(change, workspace=ws, **kwargs)


def test_a_clean_change_is_verified_merged_and_promotes_its_contracts(tmp_path: Path) -> None:
    change, ws = _setup(tmp_path)
    registry = _Registry()
    events: list[tuple[str, dict[str, Any]]] = []
    runner = _Runner(_result(), _result(), _result())

    result = _verify(
        change, ws, registry=registry, contract_ids=["billing"], acceptance_refs=["tests/test_billing.py"], runner=runner,
        emit=lambda kind, payload: events.append((kind, payload)),
    )

    assert result is None
    assert ws.ops == ["merge"]
    assert registry.promoted == [("billing", "VERIFIED")]
    assert [argv[2] for argv in runner.calls] == ["ruff", "mypy", "pytest"]
    assert [p["gate"] for k, p in events if k == "GATE_RESULT"] == ["scope", "lint", "types", "tests", "merge"]
    assert all(p["passed"] for _, p in events)


def test_files_outside_the_allowed_set_are_a_policy_violation_and_are_reverted(tmp_path: Path) -> None:
    change, ws = _setup(tmp_path, files=["src/billing.py", "src/secrets_store.py"])
    result = _verify(change, ws, allowed_files=["src/billing.py"], runner=_Runner())
    assert result.failure_class.value == "POLICY_VIOLATION"
    assert "outside the allowed files" in ws.blobs.get(result.evidence_ref).decode()
    assert ws.ops == ["revert"]  # nothing is merged


def test_a_deleted_test_is_a_policy_violation(tmp_path: Path) -> None:
    change, ws = _setup(tmp_path, files=["src/billing.py"])
    change.files_touched.append("tests/test_billing.py")  # touched but absent from the worktree: deleted
    result = _verify(change, ws, runner=_Runner())
    assert result.failure_class.value == "POLICY_VIOLATION"
    assert "deleted" in ws.blobs.get(result.evidence_ref).decode()


def test_weakened_tests_and_secrets_in_the_diff_are_policy_violations(tmp_path: Path) -> None:
    diff = (
        "+++ b/tests/test_billing.py\n-    assert total == 5\n-    assert tax == 1\n+    assert total\n+@pytest.mark.skip\n"
        "+++ b/src/billing.py\n+KEY = 'sk-abcdefghijklmnopqrstuvwxyz'\n"
    )
    change, ws = _setup(tmp_path, diff=diff)
    result = _verify(change, ws, runner=_Runner())
    text = ws.blobs.get(result.evidence_ref).decode()
    assert result.failure_class.value == "POLICY_VIOLATION"
    assert "skip/xfail" in text and "assertions were removed" in text and "secret-looking" in text


def test_a_failing_test_is_requeued_as_a_local_bug_with_the_log_as_evidence(tmp_path: Path) -> None:
    change, ws = _setup(tmp_path)
    runner = _Runner(_result(), _result(), _result(1, out="FAILED tests/test_billing.py::test_charge\nAssertionError"))
    result = _verify(change, ws, acceptance_refs=["tests/test_billing.py"], runner=runner)
    assert type(result).__name__ == "Requeue" and result.failure_class.value == "LOCAL_BUG"
    assert "AssertionError" in ws.blobs.get(result.evidence_ref).decode()
    assert "merge" not in ws.ops


def test_environment_failures_are_reported_to_the_orchestrator_not_the_worker(tmp_path: Path) -> None:
    change, ws = _setup(tmp_path)
    result = _verify(change, ws, runner=_Runner(_result(127, err="uv: not found")))
    assert type(result).__name__ == "TaskOutcome" and result.failure_class.value == "ENV_INFRA"
    assert result.attempts == 1


def test_a_flaky_failure_is_rerun_once_and_passes(tmp_path: Path) -> None:
    change, ws = _setup(tmp_path, files=[])
    runner = _Runner(_result(1, out="test_fetch flaky: timed out waiting for the server"), _result())
    result = _verify(change, ws, acceptance_refs=["tests/test_net.py"], runner=runner)
    assert result is None
    assert len(runner.calls) == 2


def test_a_flaky_failure_that_repeats_becomes_a_local_bug(tmp_path: Path) -> None:
    change, ws = _setup(tmp_path, files=[])
    flaky = _result(1, out="intermittent failure")
    result = _verify(change, ws, acceptance_refs=["tests/test_net.py"], runner=_Runner(flaky, flaky))
    assert result.failure_class.value == "LOCAL_BUG"


def test_a_merge_conflict_requeues_the_task(tmp_path: Path) -> None:
    change, ws = _setup(tmp_path, files=[], merge_ok=False)
    result = _verify(change, ws, runner=_Runner())
    assert type(result).__name__ == "Requeue"
    assert "merge" in ws.blobs.get(result.evidence_ref).decode().lower()


def test_a_missing_diff_blocks_the_change(tmp_path: Path) -> None:
    change, ws = _setup(tmp_path)
    change.diff_ref = "sha256:" + "0" * 64
    result = _verify(change, ws, runner=_Runner())
    assert result.failure_class.value == "POLICY_VIOLATION"


def test_blocking_reviewer_findings_send_a_risky_change_back(tmp_path: Path) -> None:
    class _Gateway:
        def model_for(self, role: Any, purpose: str, **_: Any) -> Any:
            return SimpleNamespace(invoke=lambda _p: SimpleNamespace(content='[{"blocking": true, "finding": "wrong return type"}]'))

    change, ws = _setup(tmp_path, files=[])
    result = _verify(change, ws, runner=_Runner(), gateway=_Gateway(), risky=True)
    assert result.failure_class.value == "LOCAL_BUG"
    assert "wrong return type" in ws.blobs.get(result.evidence_ref).decode()
    assert "merge" not in ws.ops


def test_unrisky_changes_skip_the_reviewer(tmp_path: Path) -> None:
    class _Gateway:
        def model_for(self, *_a: Any, **_k: Any) -> Any:
            raise AssertionError("the reviewer must not be consulted")

    change, ws = _setup(tmp_path, files=[])
    assert _verify(change, ws, runner=_Runner(), gateway=_Gateway(), risky=False) is None


@pytest.mark.parametrize(
    ("diff", "expected"),
    [
        ("+++ b/src/a.py\n+x = 1\n", []),
        ("+++ b/tests/test_a.py\n-    assert x\n+    assert x\n", []),
        ("+++ b/tests/test_a.py\n+@pytest.mark.xfail\n", ["a skip/xfail was added to tests/test_a.py"]),
        ("+++ b/src/a.py\n+TOKEN = 'AKIAABCDEFGHIJKLMNOP'\n", ["a secret-looking value was added in src/a.py"]),
    ],
)
def test_scan_diff(diff: str, expected: list[str]) -> None:
    assert scan_diff(diff) == expected
