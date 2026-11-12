# FILE: tests/m5_shared/workspace/test_workspace.py
# ROLE: Tests that prove src/asf/m5_shared/workspace/workspace.py meets its DONE WHEN conditions.
# ARCH REF: M5; p09 Artifact & Workspace Store; IF-15 WorkspaceOps; D-04 @task side effects; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/workspace/workspace.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/workspace/workspace.py: Workspace (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/workspace/test_workspace.py` on Windows and Linux once src/asf/m5_shared/workspace/workspace.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/workspace/test_workspace.py` and `uv run mypy tests/m5_shared/workspace/test_workspace.py` are clean.

import subprocess
from pathlib import Path
from types import SimpleNamespace

from asf.m5_shared.workspace.workspace import Workspace


def test_workspace_meets_contract(tmp_path: Path) -> None:
    """Prove Workspace behaves as declared in src/asf/m5_shared/workspace/workspace.py."""
    # Initialize a test git repository
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)  # noqa: S603, S607
    subprocess.run(["git", "config", "user.name", "ASF Test"], cwd=tmp_path, check=True, capture_output=True)  # noqa: S603, S607
    subprocess.run(["git", "config", "user.email", "test@asf.local"], cwd=tmp_path, check=True, capture_output=True)  # noqa: S603, S607

    init_file = tmp_path / "hello.txt"
    init_file.write_text("initial commit\n", encoding="utf-8")
    subprocess.run(["git", "add", "hello.txt"], cwd=tmp_path, check=True, capture_output=True)  # noqa: S603, S607
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)  # noqa: S603, S607

    ws = Workspace(tmp_path)

    # 1. CREATE_WORKTREE
    op_create = SimpleNamespace(
        kind=SimpleNamespace(value="create_worktree"),
        task_id="task-1",
        branch="feature-1",
        base_commit="HEAD",
    )
    res_create = ws.apply(op_create)  # type: ignore[arg-type]
    assert res_create.ok is True
    assert res_create.worktree_path is not None
    wt_path = Path(res_create.worktree_path)
    assert wt_path.is_dir()

    # Make a commit in the worktree
    (wt_path / "feature.txt").write_text("feature content\n", encoding="utf-8")
    subprocess.run(["git", "add", "feature.txt"], cwd=wt_path, check=True, capture_output=True)  # noqa: S603, S607
    subprocess.run(["git", "commit", "-m", "add feature"], cwd=wt_path, check=True, capture_output=True)  # noqa: S603, S607

    # 2. DIFF
    op_diff = SimpleNamespace(
        kind=SimpleNamespace(value="diff"),
        task_id="task-1",
        branch="feature-1",
        base_commit="HEAD",
    )
    res_diff = ws.apply(op_diff)  # type: ignore[arg-type]
    assert res_diff.ok is True
    assert res_diff.diff_ref is not None
    assert res_diff.diff_ref.startswith("sha256:")

    # 3. MERGE
    op_merge = SimpleNamespace(
        kind=SimpleNamespace(value="merge"),
        task_id=None,
        branch="feature-1",
        base_commit=None,
    )
    res_merge = ws.apply(op_merge)  # type: ignore[arg-type]
    assert res_merge.ok is True
    assert res_merge.commit is not None

    # Verify merged file exists in main repo
    assert (tmp_path / "feature.txt").is_file()

    # 4. TAG
    op_tag = SimpleNamespace(
        kind=SimpleNamespace(value="tag"),
        task_id="task-1",
        branch="v1.0.0",
        base_commit=None,
    )
    res_tag = ws.apply(op_tag)  # type: ignore[arg-type]
    assert res_tag.ok is True
    assert res_tag.commit is not None

    # 5. GC
    pruned = ws.gc()
    assert pruned >= 0


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()  # noqa: S603, S607


def _repo(tmp_path: Path) -> Workspace:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "ASF Test")
    _git(tmp_path, "config", "user.email", "test@asf.local")
    (tmp_path / "hello.txt").write_text("v1\n", encoding="utf-8")
    _git(tmp_path, "add", "hello.txt")
    _git(tmp_path, "commit", "-m", "init")
    return Workspace(tmp_path)


def _op(kind: str, task_id: str, **extra: object) -> SimpleNamespace:
    return SimpleNamespace(kind=SimpleNamespace(value=kind), task_id=task_id, branch=extra.get("branch"), base_commit=extra.get("base_commit"))


def test_reset_to_base_cleans_the_task_worktree_and_leaves_the_main_checkout_alone(tmp_path: Path) -> None:
    ws = _repo(tmp_path)
    created = ws.apply(_op("create_worktree", "t1", branch="task/t1", base_commit="HEAD"))  # type: ignore[arg-type]
    assert created.ok and created.worktree_path
    worktree = Path(created.worktree_path)
    (worktree / "hello.txt").write_text("interrupted edit\n", encoding="utf-8")
    (worktree / "stray.txt").write_text("untracked\n", encoding="utf-8")
    (tmp_path / "hello.txt").write_text("uncommitted work in the main checkout\n", encoding="utf-8")

    result = ws.apply(_op("reset_to_base", "t1"))  # type: ignore[arg-type]

    assert result.ok
    assert (worktree / "hello.txt").read_text(encoding="utf-8") == "v1\n"
    assert not (worktree / "stray.txt").exists()
    assert (tmp_path / "hello.txt").read_text(encoding="utf-8") == "uncommitted work in the main checkout\n"


def test_revert_acts_on_the_task_worktree_too(tmp_path: Path) -> None:
    ws = _repo(tmp_path)
    created = ws.apply(_op("create_worktree", "t2", branch="task/t2", base_commit="HEAD"))  # type: ignore[arg-type]
    worktree = Path(str(created.worktree_path))
    (worktree / "hello.txt").write_text("bad edit\n", encoding="utf-8")
    (tmp_path / "hello.txt").write_text("main edit\n", encoding="utf-8")
    assert ws.apply(_op("revert", "t2")).ok  # type: ignore[arg-type]
    assert (worktree / "hello.txt").read_text(encoding="utf-8") == "v1\n"
    assert (tmp_path / "hello.txt").read_text(encoding="utf-8") == "main edit\n"
