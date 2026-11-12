# FILE: tests/m5_shared/metrics/test_collector.py
# ROLE: Tests that prove src/asf/m5_shared/metrics/collector.py meets its DONE WHEN conditions.
# ARCH REF: M5; p10 Metrics; IF-19 MetricsSnapshot; D-24; D-19 comparability; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/metrics/collector.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/metrics/collector.py: MetricsCollector (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/metrics/test_collector.py` on Windows and Linux once src/asf/m5_shared/metrics/collector.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/metrics/test_collector.py` and `uv run mypy tests/m5_shared/metrics/test_collector.py` are clean.

import sqlite3
from pathlib import Path
from types import SimpleNamespace

from asf.m5_shared.metrics.collector import MetricsCollector


def _create_metrics_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            cost REAL NOT NULL DEFAULT 0.0,
            cost_estimated INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS call_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            task_id TEXT,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost REAL NOT NULL DEFAULT 0.0,
            duration_ms INTEGER NOT NULL DEFAULT 0,
            timestamp TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT '',
            strategy TEXT NOT NULL DEFAULT '',
            estimated INTEGER NOT NULL DEFAULT 0,
            retry_no INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tool_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            task_id TEXT,
            tool_name TEXT NOT NULL,
            duration_ms INTEGER NOT NULL DEFAULT 0,
            success INTEGER NOT NULL DEFAULT 1,
            timestamp TEXT NOT NULL,
            strategy TEXT NOT NULL DEFAULT '',
            approval TEXT NOT NULL DEFAULT '',
            sandbox_tier TEXT NOT NULL DEFAULT '',
            exit_status TEXT NOT NULL DEFAULT ''
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS limit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '{}',
            timestamp TEXT NOT NULL
        );
        """
    )
    conn.commit()


def test_metrics_collector_meets_contract(tmp_path: Path) -> None:
    """Prove MetricsCollector behaves as declared in src/asf/m5_shared/metrics/collector.py."""
    db_file = tmp_path / "metrics.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    _create_metrics_tables(conn)
    conn.execute("INSERT INTO runs (run_id, cost, cost_estimated) VALUES ('run-1', 0.0, 0)")
    conn.commit()

    store = SimpleNamespace(conn=conn)
    collector = MetricsCollector(store=store)  # type: ignore[arg-type]

    # 1. Record call
    call = SimpleNamespace(
        run_id="run-1",
        task_id="task-1",
        role="worker",
        provider="anthropic",
        model="claude-3-5-sonnet",
        strategy="tool_loop",
        tokens_in=1000,
        tokens_out=200,
        latency_ms=150,
        cost=0.05,
        source=SimpleNamespace(value="MEASURED"),
        retry_no=0,
    )
    collector.record_call(call)  # type: ignore[arg-type]

    # Verify run updated
    run_row = conn.execute("SELECT cost, cost_estimated FROM runs WHERE run_id = 'run-1'").fetchone()
    assert run_row["cost"] == 0.05
    assert run_row["cost_estimated"] == 0

    # 2. Record tool
    tool = SimpleNamespace(
        run_id="run-1",
        task_id="task-1",
        tool="compiler",
        strategy="tool_loop",
        duration_ms=45,
        exit_status="0",
        approval="auto",
        sandbox_tier="A",
    )
    collector.record_tool(tool)  # type: ignore[arg-type]

    # 3. Record limit
    limit = SimpleNamespace(
        run_id="run-1",
        kind="rate_limit",
        detail="Rate limit reached on tier T1",
    )
    collector.record_limit(limit)  # type: ignore[arg-type]

    # 4. Snapshot
    snap = collector.snapshot("run-1")
    assert snap.run_id == "run-1"
    assert snap.values["cost"] == 0.05
    assert snap.values["input_tokens"] == 1000.0
    assert snap.values["output_tokens"] == 200.0
    assert snap.values["calls"] == 1.0
    assert snap.values["tools"] == 1.0
    assert snap.values["limits"] == 1.0

    # 5. Export CSV
    export_dir = tmp_path / "csv_export"
    files = collector.export_csv("run-1", export_dir)
    assert len(files) == 3
    for f in files:
        p = Path(f)
        assert p.is_file()
        content = p.read_text(encoding="utf-8")
        assert "run-1" in content

    conn.close()


def test_role_strategy_and_the_estimate_flag_are_kept_for_comparisons(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _create_metrics_tables(conn)
    conn.execute("INSERT INTO runs (run_id) VALUES ('r1')")
    collector = MetricsCollector(SimpleNamespace(conn=conn))  # type: ignore[arg-type]
    collector.record_call(
        SimpleNamespace(
            run_id="r1", task_id="t1", role="worker", provider="local", model="m", strategy="tool_loop", tokens_in=10, tokens_out=5,
            latency_ms=7, cost=0.0, source=SimpleNamespace(value="ESTIMATED"), retry_no=2,
        )  # type: ignore[arg-type]
    )
    collector.record_tool(
        SimpleNamespace(
            run_id="r1", task_id="t1", tool="read_file", strategy="code_exec", duration_ms=3, exit_status="ok", approval="auto", sandbox_tier="A"
        )  # type: ignore[arg-type]
    )
    call = conn.execute("SELECT role, strategy, estimated, retry_no FROM call_metrics").fetchone()
    assert tuple(call) == ("worker", "tool_loop", 1, 2)
    tool = conn.execute("SELECT strategy, approval, sandbox_tier, exit_status FROM tool_metrics").fetchone()
    assert tuple(tool) == ("code_exec", "auto", "A", "ok")
