# FILE: tests/m4_execution/worker/test_worker_graph.py
# ROLE: Tests that prove src/asf/m4_execution/worker/worker_graph.py meets its DONE WHEN conditions.
# ARCH REF: M4; p07 Local Coding Worker; IF-11; IF-12; IF-14; IF-15; IF-21 ChangeSet; D-05; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m4_execution/worker/worker_graph.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m4_execution/worker/worker_graph.py: run_attempt, WorkerError (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
#   - imports from src/asf/m5_shared/workspace/workspace.py: Workspace (a real git repository for the attempt)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m4_execution/worker/test_worker_graph.py` on Windows and Linux once src/asf/m4_execution/worker/worker_graph.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m4_execution/worker/test_worker_graph.py` and `uv run mypy tests/m4_execution/worker/test_worker_graph.py` are clean.

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from asf.m4_execution.worker.worker_graph import WorkerError, run_attempt


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()  # noqa: S603, S607


def _repo(tmp_path: Path) -> tuple[Any, str]:
    from asf.m5_shared.workspace.workspace import Workspace

    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "user.email", "t@t")
    (root / "src").mkdir()
    (root / "src" / "billing.py").write_text("a = 1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    return Workspace(root), _git(root, "rev-parse", "HEAD")


class _Gateway:
    def __init__(self, worktree_edit: str = "b = 2\n") -> None:
        self.worktree_edit = worktree_edit
        self.prompts: list[str] = []

    def model_for(self, role: Any, purpose: str, **_: Any) -> Any:
        outer = self

        class _Model:
            def invoke(self, prompt: str) -> Any:
                outer.prompts.append(prompt)
                if "Result:" not in prompt:
                    return SimpleNamespace(
                        content=json.dumps({"action": "tool", "tool": "write_file", "args": {"path": "src/billing.py", "content": outer.worktree_edit}})
                    )
                return SimpleNamespace(content=json.dumps({"action": "done", "message": "wrote billing"}))

        return _Model()


class _Executor:
    def active_tier(self) -> str:
        return "B"

    def invoke(self, invocation: Any, allowed_files: list[str]) -> Any:
        target = Path(invocation.workspace_dir) / invocation.args["path"]
        target.write_text(invocation.args["content"], encoding="utf-8")
        return SimpleNamespace(status="ok", output="written")


class _Runtime:
    def __init__(self) -> None:
        self.beats: list[str] = []

    def heartbeat(self, lease_id: str) -> None:
        self.beats.append(lease_id)


def _spec(base: str, budget: int = 5000) -> Any:
    return SimpleNamespace(
        task_id="t1", goal="extend billing", acceptance_test_refs=["tests/test_billing.py"],
        capsules=[SimpleNamespace(module_id="ledger", operation="record", lines=["a", "b", "c"])],
        allowed_files=["src/billing.py"], read_only_files=[], context_budget_tokens=budget, base_commit=base,
        step_budget=SimpleNamespace(max_turns=4, wall_clock_s=60),
    )


def _lease(seconds: float = 30.0) -> Any:
    import time

    return SimpleNamespace(lease_id="lease-1", model_id="local-coder", ctx_tokens=8192, expires_at_monotonic=time.monotonic() + seconds)


def test_one_attempt_produces_a_committed_change_set(tmp_path: Path) -> None:
    ws, base = _repo(tmp_path)
    events: list[tuple[str, dict[str, Any]]] = []
    gateway = _Gateway()

    change = run_attempt(
        _spec(base), _lease(), 1, workspace=ws, gateway=gateway, executor=_Executor(),  # type: ignore[arg-type]
        emit=lambda kind, payload: events.append((kind, payload)),
    )

    assert change.task_id == "t1" and change.attempt_no == 1
    assert change.files_touched == ["src/billing.py"]
    assert "+b = 2" in ws.blobs.get(change.diff_ref).decode()
    assert "wrote billing" in change.self_report
    worktree = Path(change.worktree_path)
    assert _git(worktree, "log", "-1", "--format=%s") == "task t1 attempt 1"
    assert _git(worktree, "branch", "--show-current") == "task/t1"
    assert [k for k, _ in events] == ["TASK_RECEIVED", "STEP_STARTED", "HANDOFF_SENT"]
    assert "extend billing" in gateway.prompts[0] and "a = 1" in gateway.prompts[0]  # spec and allowed file are in the ContextPack


def test_a_retry_starts_from_a_clean_worktree_at_the_base_commit(tmp_path: Path) -> None:
    ws, base = _repo(tmp_path)
    first = run_attempt(_spec(base), _lease(), 1, workspace=ws, gateway=_Gateway("first = 1\n"), executor=_Executor())  # type: ignore[arg-type]
    (Path(first.worktree_path) / "junk.txt").write_text("leftover", encoding="utf-8")
    second = run_attempt(_spec(base), _lease(), 2, workspace=ws, gateway=_Gateway("second = 2\n"), executor=_Executor())  # type: ignore[arg-type]
    assert second.files_touched == ["src/billing.py"]
    assert not (Path(second.worktree_path) / "junk.txt").exists()
    assert "second = 2" in ws.blobs.get(second.diff_ref).decode() and "first = 1" not in ws.blobs.get(second.diff_ref).decode()


def test_the_lease_is_kept_alive_while_the_strategy_runs(tmp_path: Path) -> None:
    ws, base = _repo(tmp_path)
    runtime = _Runtime()

    class _Slow(_Gateway):
        def model_for(self, role: Any, purpose: str, **_: Any) -> Any:
            import time

            time.sleep(1.3)  # long enough for at least one beat at the minimum interval
            return super().model_for(role, purpose)

    run_attempt(_spec(base), _lease(3.0), 1, workspace=ws, gateway=_Slow(), executor=_Executor(), runtime=runtime)  # type: ignore[arg-type]
    assert runtime.beats and set(runtime.beats) == {"lease-1"}


def test_must_have_context_that_does_not_fit_raises_context_overflow(tmp_path: Path) -> None:
    ws, base = _repo(tmp_path)
    with pytest.raises(Exception) as info:  # noqa: PT011 - ContextOverflow lives in contracts, which this test does not import
        run_attempt(_spec(base, budget=3), _lease(), 1, workspace=ws, gateway=_Gateway(), executor=_Executor())  # type: ignore[arg-type]
    assert type(info.value).__name__ == "ContextOverflow"


def test_failing_to_create_a_worktree_is_a_worker_error(tmp_path: Path) -> None:
    ws, base = _repo(tmp_path)
    with pytest.raises(WorkerError):
        run_attempt(_spec("not-a-commit"), _lease(), 1, workspace=ws, gateway=_Gateway(), executor=_Executor())  # type: ignore[arg-type]
