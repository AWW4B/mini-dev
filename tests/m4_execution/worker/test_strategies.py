# FILE: tests/m4_execution/worker/test_strategies.py
# ROLE: Tests that prove src/asf/m4_execution/worker/strategies.py meets its DONE WHEN conditions.
# ARCH REF: M4; p07; D-09 worker strategies; D-19; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m4_execution/worker/strategies.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m4_execution/worker/strategies.py: run_strategy, WorkerStrategyName, WorkerBlocked, WorkerFormatError (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m4_execution/worker/test_strategies.py` on Windows and Linux once src/asf/m4_execution/worker/strategies.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m4_execution/worker/test_strategies.py` and `uv run mypy tests/m4_execution/worker/test_strategies.py` are clean.

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from asf.m4_execution.worker.strategies import WorkerBlocked, WorkerFormatError, WorkerStrategyName, run_strategy


class _Gateway:
    """Replays scripted model replies and records every prompt."""

    def __init__(self, *replies: Any) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    def model_for(self, role: Any, purpose: str, **_: Any) -> Any:
        outer = self

        class _Model:
            def invoke(self, prompt: str) -> Any:
                outer.prompts.append(prompt)
                reply = outer.replies.pop(0)
                if isinstance(reply, Exception):
                    raise reply
                return SimpleNamespace(content=reply if isinstance(reply, str) else json.dumps(reply))

        return _Model()


class _Executor:
    def __init__(self, tier: str = "A", ok: bool = True) -> None:
        self.tier = tier
        self.ok = ok
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def active_tier(self) -> str:
        return self.tier

    def invoke(self, invocation: Any, allowed_files: list[str]) -> Any:
        self.calls.append((invocation.tool, invocation.args))
        return SimpleNamespace(status="ok" if self.ok else "denied", output="file contents" if self.ok else "outside allowed files")


def _spec(max_turns: int = 4, wall_clock_s: int = 60) -> Any:
    return SimpleNamespace(
        task_id="t1",
        goal="write src/billing.py",
        allowed_files=["src/billing.py"],
        read_only_files=[],
        acceptance_test_refs=["tests/test_billing.py"],
        capsules=[SimpleNamespace(module_id="ledger", operation="record", lines=["record(entry) -> None", "raises LedgerError", "idempotent"])],
        step_budget=SimpleNamespace(max_turns=max_turns, wall_clock_s=wall_clock_s),
    )


def _run(name: WorkerStrategyName, gateway: _Gateway, executor: _Executor, tmp_path: Path, spec: Any = None) -> str:
    return run_strategy(name, spec or _spec(), str(tmp_path), gateway=gateway, executor=executor, context="CTX")  # type: ignore[arg-type]


def test_tool_loop_calls_tools_until_the_model_says_done(tmp_path: Path) -> None:
    gateway = _Gateway(
        {"action": "tool", "tool": "read_file", "args": {"path": "src/billing.py"}},
        {"action": "tool", "tool": "write_file", "args": {"path": "src/billing.py", "content": "x = 1"}},
        {"action": "done", "message": "implemented"},
    )
    executor = _Executor()
    report = _run("tool_loop", gateway, executor, tmp_path)
    assert "3 step(s)" in report and "implemented" in report
    assert [c[0] for c in executor.calls] == ["read_file", "write_file"]
    assert "file contents" in gateway.prompts[1]  # the observation is fed back
    assert "ledger.record" in gateway.prompts[0] and "CTX" in gateway.prompts[0] and "src/billing.py" in gateway.prompts[0]


def test_a_malformed_reply_is_repaired_within_two_retries(tmp_path: Path) -> None:
    gateway = _Gateway("no json here", "still { not json", {"action": "done", "message": "ok"})
    assert "ok" in _run("tool_loop", gateway, _Executor(), tmp_path)
    assert "rejected" in gateway.prompts[1]


def test_three_malformed_replies_raise_a_format_error(tmp_path: Path) -> None:
    gateway = _Gateway("a", "b", "c")
    with pytest.raises(WorkerFormatError):
        _run("tool_loop", gateway, _Executor(), tmp_path)


def test_blocked_is_surfaced_to_the_orchestrator(tmp_path: Path) -> None:
    gateway = _Gateway({"action": "blocked", "message": "CONTRACT_GAP: ledger has no refund operation"})
    with pytest.raises(WorkerBlocked) as info:
        _run("tool_loop", gateway, _Executor(), tmp_path)
    assert "CONTRACT_GAP" in str(info.value)


def test_the_turn_budget_is_enforced(tmp_path: Path) -> None:
    gateway = _Gateway(*[{"action": "tool", "tool": "list_files", "args": {"path": "."}}] * 3)
    with pytest.raises(WorkerBlocked) as info:
        _run("tool_loop", gateway, _Executor(), tmp_path, _spec(max_turns=3))
    assert "SPEC_TOO_LARGE" in str(info.value)
    assert len(gateway.prompts) == 3


def test_an_unknown_action_is_reported_back_and_costs_a_turn(tmp_path: Path) -> None:
    gateway = _Gateway({"action": "dance"}, {"action": "done", "message": "fine"})
    assert "fine" in _run("tool_loop", gateway, _Executor(), tmp_path)
    assert "invalid action" in gateway.prompts[1]


def test_whole_file_edit_writes_every_file_through_the_tool_executor(tmp_path: Path) -> None:
    gateway = _Gateway({"action": "done", "message": "rewrote it", "files": {"src/billing.py": "def charge(): ...\n"}})
    executor = _Executor()
    report = _run("whole_file_edit", gateway, executor, tmp_path)
    assert "1 file" in report
    assert executor.calls == [("write_file", {"path": "src/billing.py", "content": "def charge(): ...\n"})]


def test_whole_file_edit_fails_when_the_executor_denies_the_write(tmp_path: Path) -> None:
    gateway = _Gateway({"action": "done", "message": "m", "files": {"src/other.py": "x"}})
    with pytest.raises(WorkerFormatError):
        _run("whole_file_edit", gateway, _Executor(ok=False), tmp_path)


def test_diff_edit_applies_a_unified_diff_to_an_allowed_file(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "billing.py").write_text("a = 1\n", encoding="utf-8")
    diff = "--- a/src/billing.py\n+++ b/src/billing.py\n@@ -1 +1,2 @@\n a = 1\n+b = 2\n"
    report = _run("diff_edit", _Gateway({"action": "done", "message": "added b", "diff": diff}), _Executor(), tmp_path)
    assert "1 file" in report
    assert (tmp_path / "src" / "billing.py").read_text(encoding="utf-8") == "a = 1\nb = 2\n"
    assert not (tmp_path / ".asf_worker.patch").exists()


def test_diff_edit_rejects_files_outside_the_allowed_set_before_applying(tmp_path: Path) -> None:
    (tmp_path / "other.py").write_text("a = 1\n", encoding="utf-8")
    diff = "--- a/other.py\n+++ b/other.py\n@@ -1 +1,2 @@\n a = 1\n+evil = 1\n"
    with pytest.raises(WorkerFormatError):
        _run("diff_edit", _Gateway({"action": "done", "message": "m", "diff": diff}), _Executor(), tmp_path)
    assert (tmp_path / "other.py").read_text(encoding="utf-8") == "a = 1\n"


def test_diff_edit_reports_a_diff_that_does_not_apply(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "billing.py").write_text("something else\n", encoding="utf-8")
    diff = "--- a/src/billing.py\n+++ b/src/billing.py\n@@ -1 +1,2 @@\n a = 1\n+b = 2\n"
    with pytest.raises(WorkerFormatError):
        _run("diff_edit", _Gateway({"action": "done", "message": "m", "diff": diff}), _Executor(), tmp_path)


@pytest.mark.parametrize("tier", ["B", "C"])
def test_code_exec_falls_back_to_the_tool_loop_without_a_tier_a_sandbox(tmp_path: Path, tier: str) -> None:
    gateway = _Gateway({"action": "done", "message": "via loop"})
    assert "tool_loop" in _run("code_exec", gateway, _Executor(tier=tier), tmp_path)


def test_an_unknown_strategy_is_a_programming_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _run("magic", _Gateway(), _Executor(), tmp_path)  # type: ignore[arg-type]
