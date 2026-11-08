# FILE: tests/m5_shared/events/test_fanout.py
# ROLE: Tests that prove src/asf/m5_shared/events/fanout.py meets its DONE WHEN conditions.
# ARCH REF: M5; p10 fan-out; IF-18 EventSubscribe; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/events/fanout.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/events/fanout.py: EventFanout (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/events/test_fanout.py` on Windows and Linux once src/asf/m5_shared/events/fanout.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/events/test_fanout.py` and `uv run mypy tests/m5_shared/events/test_fanout.py` are clean.

from types import SimpleNamespace
from typing import Any

from asf.m5_shared.events.fanout import EventFanout


def test_event_fanout_meets_contract() -> None:
    """Prove EventFanout behaves as declared in src/asf/m5_shared/events/fanout.py."""
    e1 = SimpleNamespace(run_id="run-1", seq=1, kind="step_started")
    e2 = SimpleNamespace(run_id="run-1", seq=2, kind="model_call")
    e3 = SimpleNamespace(run_id="run-1", seq=3, kind="run_completed")

    class FakeEventLog:
        def __init__(self, events: list[Any]) -> None:
            self.events = events

        def read(self, run_id: str, after_seq: int = 0, limit: int = 500, visibility: Any = None) -> list[Any]:
            return [e for e in self.events if e.run_id == run_id and e.seq > after_seq][:limit]

    log = FakeEventLog([e1, e2, e3])
    fanout = EventFanout(log=log, poll_interval=0.0)  # type: ignore[arg-type]

    # Follow all events from start
    collected: list[Any] = []
    for evt in fanout.follow("run-1", after_seq=0):
        collected.append(evt)
        if evt.seq == 3:
            fanout.stop()
    assert [e.seq for e in collected] == [1, 2, 3]

    # Resume from cursor
    fanout._stopped = False
    collected_cursor: list[Any] = []
    for evt in fanout.follow("run-1", after_seq=2):
        collected_cursor.append(evt)
        if evt.seq == 3:
            fanout.stop()
    assert [e.seq for e in collected_cursor] == [3]

    # Filter by kinds
    fanout._stopped = False
    collected_filtered: list[Any] = []
    for evt in fanout.follow("run-1", after_seq=0, kinds={"step_started"}):  # type: ignore[arg-type]
        collected_filtered.append(evt)
        # Stop after receiving the expected event
        fanout.stop()
    assert len(collected_filtered) == 1
    assert collected_filtered[0].kind == "step_started"
