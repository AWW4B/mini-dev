# FILE: tests/cli/views/test_task_tree_view.py
# ROLE: Tests that prove src/asf/cli/views/task_tree_view.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02; p06; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/views/task_tree_view.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/views/task_tree_view.py: TaskTreeView (unit under test)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (capture the output)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (a real store with rows)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/views/test_task_tree_view.py` on Windows and Linux once src/asf/cli/views/task_tree_view.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/views/test_task_tree_view.py` and `uv run mypy tests/cli/views/test_task_tree_view.py` are clean.

import io
import json
from pathlib import Path
from typing import Any

from asf.cli.ui.render import OutputMode, Renderer
from asf.cli.views.task_tree_view import TaskTreeView
from asf.m5_shared.state_store.store import StateStore


def _store(tmp_path: Path) -> StateStore:
    store = StateStore.open(tmp_path / "state.db")
    with store.conn:
        store.conn.execute(
            "INSERT INTO runs (run_id, project_id, status, version, created_at, last_activity, cost, cost_estimated, payload) "
            "VALUES ('run1', 'p', 'RUNNING', 1, 't', 't', 0, 0, '{}')"
        )
    return store


def _task(store: StateStore, task_id: str, parent: str | None, state: str, run: str = "run1", **counters: int) -> None:
    payload = {"id": task_id, "run_id": run, "parent_id": parent, "kind": "composite", "goal": f"goal of {task_id}", "idempotency_key": task_id, "state": state, "counters": counters}
    with store.conn:
        store.conn.execute(
            "INSERT INTO tasks (task_id, run_id, parent_id, state, kind, version, title, payload) VALUES (?, ?, ?, ?, 'composite', 1, 'g', ?)",
            (task_id, run, parent, state, json.dumps(payload)),
        )


def _view(store: StateStore, mode: OutputMode = OutputMode.JSON, **kw: Any) -> tuple[TaskTreeView, io.StringIO]:
    out = io.StringIO()
    return TaskTreeView(Renderer(mode, stdout=out, stderr=io.StringIO()), "run1", store=store, **kw), out


def test_the_tree_is_built_from_parent_links_with_states_and_counters(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _task(store, "root", None, "DECOMPOSED")
    _task(store, "a", "root", "RUNNING", attempts=2)
    _task(store, "b", "root", "VERIFIED")
    _task(store, "a.1", "a", "READY", split_attempts=1, repair_rounds=1)
    view, out = _view(store)
    view.render_once()
    (root,) = json.loads(out.getvalue())["nodes"]
    assert root["state"] == "DECOMPOSED" and [c["state"] for c in root["children"]] == ["RUNNING", "VERIFIED"]
    a = root["children"][0]
    assert "attempts 2/3" in a["label"] and a["children"][0]["label"].endswith("(attempts 0/3, splits 1, repairs 1)")


def test_nodes_whose_parent_is_unknown_become_roots_and_replan_runs_are_included(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _task(store, "orphan", "ghost", "READY")
    _task(store, "r1-root", None, "DECOMPOSED", run="run1-r1")
    _task(store, "elsewhere", None, "READY", run="other")
    _, nodes = _view(store)[0].build()
    assert sorted(n["label"].split(":")[0] for n in nodes) == ["orphan", "r1-root"]


def test_plain_output_shows_the_hierarchy(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _task(store, "root", None, "DECOMPOSED")
    _task(store, "a", "root", "RUNNING")
    view, out = _view(store, OutputMode.PLAIN)
    view.render_once()
    assert "- root: goal of root" in out.getvalue() and "  - a: goal of a" in out.getvalue() and "[RUNNING]" in out.getvalue()


def test_an_empty_run_renders_an_empty_tree(tmp_path: Path) -> None:
    view, out = _view(_store(tmp_path))
    view.render_once()
    assert json.loads(out.getvalue())["nodes"] == []


def test_live_refreshes_until_ctrl_c_and_only_exits_the_view(tmp_path: Path) -> None:
    store = _store(tmp_path)
    ticks: list[float] = []

    def sleep(seconds: float) -> None:
        ticks.append(seconds)
        if len(ticks) == 3:
            raise KeyboardInterrupt

    view, out = _view(store, OutputMode.PLAIN, sleep=sleep, interval_s=0.5)
    view.live()
    assert ticks == [0.5, 0.5, 0.5] and out.getvalue().count("Tasks of run run1") == 3 and "view closed" in out.getvalue()
