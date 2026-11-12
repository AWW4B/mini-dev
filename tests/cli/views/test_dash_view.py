# FILE: tests/cli/views/test_dash_view.py
# ROLE: Tests that prove src/asf/cli/views/dash_view.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02 Resource Dashboard; IF-19; IF-20; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/views/dash_view.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/views/dash_view.py: DashView (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/views/test_dash_view.py` on Windows and Linux once src/asf/cli/views/dash_view.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/views/test_dash_view.py` and `uv run mypy tests/cli/views/test_dash_view.py` are clean.

import io
import json
from pathlib import Path
from typing import Any

from asf.cli.ui.render import OutputMode, Renderer
from asf.cli.views.dash_view import DashView
from asf.m5_shared.state_store.store import StateStore


def _store(tmp_path: Path, estimated: int = 0) -> StateStore:
    store = StateStore.open(tmp_path / "s.db")
    with store.conn:
        store.conn.execute(
            "INSERT INTO runs (run_id, project_id, status, version, created_at, last_activity, cost, cost_estimated, payload) "
            "VALUES ('run1', 'proj', 'RUNNING', 1, 't', '2026-11-12', 1.25, ?, '{}')",
            (estimated,),
        )
        for i, state in enumerate(["READY", "READY", "RUNNING", "VERIFIED"]):
            store.conn.execute(
                "INSERT INTO tasks (task_id, run_id, state, kind, version, title, payload) VALUES (?, 'run1', ?, 'leaf', 1, 'g', '{}')", (f"t{i}", state)
            )
        store.conn.execute(
            "INSERT INTO call_metrics (run_id, provider, model, input_tokens, output_tokens, cost, duration_ms, timestamp) "
            "VALUES ('run1', 'local', 'm', 1200, 300, 1.25, 50, 't')"
        )
        store.conn.execute("INSERT INTO decisions (decision_id, run_id, topic, status, version, payload) VALUES ('d1', 'run1', 'clarify', 'PENDING', 1, '{}')")
    return store


def _view(store: StateStore, **kw: Any) -> tuple[DashView, io.StringIO]:
    out = io.StringIO()
    return DashView(Renderer(OutputMode.JSON, stdout=out, stderr=io.StringIO()), "run1", store=store, **kw), out


def _docs(out: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in out.getvalue().splitlines()]


def test_the_dashboard_shows_status_tokens_cost_queue_and_waiting_decisions(tmp_path: Path) -> None:
    view, out = _view(_store(tmp_path))
    view.render_once()
    record, queue = _docs(out)
    data = record["data"]
    assert record["title"] == "Run run1" and data["status"] == "RUNNING" and data["project"] == "proj"
    assert data["tokens in / out"] == "1200 / 300" and data["cost"] == "1.2500" and data["calls"] == 1
    assert data["decisions waiting"] == 1 and "factory run pause" in data["controls"] and data["RAM free"].endswith("GB")
    assert queue["rows"] == [{"state": "READY", "tasks": 2}, {"state": "RUNNING", "tasks": 1}, {"state": "VERIFIED", "tasks": 1}]


def test_an_estimated_cost_is_flagged(tmp_path: Path) -> None:
    view, out = _view(_store(tmp_path, estimated=1))
    view.render_once()
    assert _docs(out)[0]["data"]["cost"].endswith(" EST")


def test_the_snapshot_is_a_real_metrics_snapshot(tmp_path: Path) -> None:
    run_id, metrics, queue, info, pending = _view(_store(tmp_path))[0].snapshot()
    assert run_id == "run1" and metrics.values["input_tokens"] == 1200.0 and queue["READY"] == 2 and pending == 1 and info["status"] == "RUNNING"


def test_live_refreshes_until_ctrl_c(tmp_path: Path) -> None:
    ticks: list[float] = []

    def sleep(seconds: float) -> None:
        ticks.append(seconds)
        if len(ticks) == 2:
            raise KeyboardInterrupt

    view, out = _view(_store(tmp_path), sleep=sleep, interval_s=0.25)
    view.live()
    assert ticks == [0.25, 0.25] and sum(1 for d in _docs(out) if d.get("title") == "Run run1") == 2
