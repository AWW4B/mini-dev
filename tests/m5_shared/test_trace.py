# FILE: tests/m5_shared/test_trace.py
# ROLE: Tests that prove src/asf/m5_shared/trace.py meets its DONE WHEN conditions.
# ARCH REF: M5; p12 Observability; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/trace.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/trace.py: start_trace, stop_trace, trace_event, set_run, current_trace_paths, clip (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/test_trace.py` on Windows and Linux once src/asf/m5_shared/trace.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/test_trace.py` and `uv run mypy tests/m5_shared/test_trace.py` are clean.

import json
import logging
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from asf.m5_shared.trace import clip, current_trace_paths, set_run, start_trace, stop_trace, trace_event


@pytest.fixture(autouse=True)
def _closed() -> Iterator[None]:
    stop_trace()
    yield
    stop_trace()


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_an_event_records_where_it_happened_and_which_run(tmp_path: Path) -> None:
    path = start_trace(tmp_path, "run-1")
    trace_event("demo", "something", size=3, text="hello")
    rows = _lines(path)
    assert rows[0]["event"] == "started"
    row = rows[-1]
    assert (row["component"], row["event"], row["run_id"]) == ("demo", "something", "run-1")
    assert row["data"] == {"size": 3, "text": "hello"}
    assert "test_trace.py" in row["where"] and "test_an_event_records_where_it_happened" in row["where"]
    assert "something" in (tmp_path / ".factory" / "logs" / "trace.log").read_text(encoding="utf-8")


def test_long_text_is_clipped_with_its_length_and_secrets_are_redacted(tmp_path: Path) -> None:
    path = start_trace(tmp_path, "r")
    trace_event("demo", "big", text="x" * 5000, key="sk-" + "a" * 40)
    data = _lines(path)[-1]["data"]
    assert data["text"].endswith("...[5000 chars]") and len(data["text"]) < 700
    assert "a" * 40 not in data["key"]
    assert clip(["a"] * 100)[-1] == "...[100 items]"


def test_library_log_records_land_in_the_trace_with_their_call_site(tmp_path: Path) -> None:
    path = start_trace(tmp_path, "r")
    logging.getLogger("asf.demo").warning("watch out %s", 7)
    row = _lines(path)[-1]
    assert (row["component"], row["event"], row["data"]["message"]) == ("log", "warning", "watch out 7")
    assert "test_trace.py" in row["where"]


def test_events_from_other_threads_are_recorded_in_order(tmp_path: Path) -> None:
    path = start_trace(tmp_path, "r")
    threads = [threading.Thread(target=trace_event, args=("t", "e"), kwargs={"n": i}, name=f"w{i}") for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rows = [r for r in _lines(path) if r["component"] == "t"]
    assert sorted(r["data"]["n"] for r in rows) == [0, 1, 2, 3, 4] and {r["thread"] for r in rows} == {f"w{i}" for i in range(5)}
    seqs = [r["seq"] for r in _lines(path)]
    assert seqs == sorted(seqs)


def test_nothing_is_written_without_a_trace_and_off_disables_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trace_event("demo", "ignored")
    assert current_trace_paths() is None
    monkeypatch.setenv("FACTORY_TRACE", "off")
    start_trace(tmp_path, "r")
    trace_event("demo", "ignored")
    assert not (tmp_path / ".factory" / "logs" / "trace.jsonl").exists()
    set_run(None)


def test_a_log_record_raised_while_redacting_does_not_recurse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With the trace on, a failing redaction (which logs) hung the process: the log handler redacted again, forever."""
    import asf.m5_shared.trace as trace

    path = start_trace(tmp_path, "r")

    def broken(text: str) -> str:
        logging.getLogger("asf.redaction").warning("redaction failed")
        raise RuntimeError("boom")

    monkeypatch.setattr(trace, "redact_text", broken)
    trace_event("demo", "x", text="hello")
    logging.getLogger("asf.demo").warning("still fine")
    assert path.exists()
