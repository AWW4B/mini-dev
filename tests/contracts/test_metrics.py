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


from asf.contracts.metrics import CallMetric, LimitEvent, MetricsSnapshot, ResourceAdvisory, ToolMetric, ValueSource  # noqa: F401


def test_value_source_meets_contract() -> None:
    """Prove ValueSource behaves as declared in src/asf/contracts/metrics.py."""
    raise NotImplementedError("write this test before implementing ValueSource")

def test_call_metric_meets_contract() -> None:
    """Prove CallMetric behaves as declared in src/asf/contracts/metrics.py."""
    raise NotImplementedError("write this test before implementing CallMetric")

def test_tool_metric_meets_contract() -> None:
    """Prove ToolMetric behaves as declared in src/asf/contracts/metrics.py."""
    raise NotImplementedError("write this test before implementing ToolMetric")

def test_limit_event_meets_contract() -> None:
    """Prove LimitEvent behaves as declared in src/asf/contracts/metrics.py."""
    raise NotImplementedError("write this test before implementing LimitEvent")

def test_metrics_snapshot_meets_contract() -> None:
    """Prove MetricsSnapshot behaves as declared in src/asf/contracts/metrics.py."""
    raise NotImplementedError("write this test before implementing MetricsSnapshot")

def test_resource_advisory_meets_contract() -> None:
    """Prove ResourceAdvisory behaves as declared in src/asf/contracts/metrics.py."""
    raise NotImplementedError("write this test before implementing ResourceAdvisory")
