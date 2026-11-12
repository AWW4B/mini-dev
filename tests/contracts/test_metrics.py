# FILE: tests/contracts/test_metrics.py
# ROLE: Tests that prove src/asf/contracts/metrics.py meets its DONE WHEN conditions.
# ARCH REF: p10 Metrics; IF-19; IF-20; D-24; D-27; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/metrics.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/metrics.py: ValueSource, CallMetric, ToolMetric, LimitEvent, MetricsSnapshot, ResourceAdvisory (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_metrics.py` on Windows and Linux once src/asf/contracts/metrics.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_metrics.py` and `uv run mypy tests/contracts/test_metrics.py` are clean.


from typing import Any

import pytest
from pydantic import ValidationError

from asf.contracts.metrics import CallMetric, LimitEvent, MetricsSnapshot, ResourceAdvisory, ToolMetric, ValueSource


def _call(**over: Any) -> dict[str, Any]:
    return {
        "run_id": "r1", "task_id": None, "role": "worker", "provider": "local", "model": "m", "strategy": "tool_loop",
        "tokens_in": 10, "tokens_out": 5, "latency_ms": 120, "cost": 0.0, "source": "MEASURED", **over,
    }


def test_value_source_values() -> None:
    assert {v.value for v in ValueSource} == {"MEASURED", "ESTIMATED"}


def test_call_metric_defaults_and_nullable_task_id() -> None:
    m = CallMetric.model_validate(_call())
    assert m.retry_no == 0
    assert m.task_id is None
    assert CallMetric.model_validate(_call(task_id="t1")).task_id == "t1"


def test_call_metric_rejects_unknown_source_and_missing_fields() -> None:
    with pytest.raises(ValidationError):
        CallMetric.model_validate(_call(source="GUESSED"))
    data = _call()
    del data["latency_ms"]
    with pytest.raises(ValidationError):
        CallMetric.model_validate(data)


def test_call_metric_round_trip() -> None:
    m = CallMetric.model_validate(_call(cost=0.12, source="ESTIMATED", retry_no=2))
    assert CallMetric.model_validate_json(m.model_dump_json()) == m


def test_tool_metric_requires_all_fields() -> None:
    data = {
        "run_id": "r1", "task_id": "t1", "tool": "read_file", "strategy": "code_exec",
        "duration_ms": 4, "exit_status": "ok", "approval": "auto", "sandbox_tier": "A",
    }
    assert ToolMetric.model_validate(data).strategy == "code_exec"
    for missing in data:
        partial = dict(data)
        del partial[missing]
        with pytest.raises(ValidationError):
            ToolMetric.model_validate(partial)


def test_limit_event() -> None:
    ev = LimitEvent.model_validate({"run_id": "r1", "kind": "budget", "detail": "tokens"})
    assert ev.kind == "budget"
    with pytest.raises(ValidationError):
        LimitEvent.model_validate({"run_id": "r1", "kind": "budget"})


def test_snapshot_defaults_and_values_keep_their_source() -> None:
    snap = MetricsSnapshot.model_validate({"run_id": None, "values": {"tokens": 5.0}, "sources": {"tokens": "MEASURED"}})
    assert snap.advisories == []
    assert snap.sources["tokens"] is ValueSource.MEASURED
    assert MetricsSnapshot.model_validate_json(snap.model_dump_json()) == snap


def test_resource_advisory_defaults() -> None:
    adv = ResourceAdvisory.model_validate({"kind": "vram", "severity": "soft", "detail": "low"})
    assert adv.max_slots is None
    assert ResourceAdvisory.model_validate({"kind": "vram", "severity": "hard", "detail": "x", "max_slots": 1}).max_slots == 1
