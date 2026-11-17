# FILE: tests/m5_shared/memory/test_hooks.py
# ROLE: Tests for src/asf/m5_shared/memory/hooks.py.
# ARCH REF: M5; p12 Context & Memory Service; docs/architecture/MEMORY_ARCHITECTURE.md
# OWNS: Tests of hooks
# DOES NOT OWN: Production code
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/memory/hooks.py: MemoryHooks (unit under test)
#   - imports from src/asf/m5_shared/memory/device_budget.py: DeviceSnapshot, load_memory_config, plan_device (a fixed device)
#   - imports from src/asf/m5_shared/memory/store.py: MemoryRecord (records)
#   - imports from tests/conftest.py: fake_paths (isolated app directories)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/memory/test_hooks.py` on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/memory/test_hooks.py` and `uv run mypy tests/m5_shared/memory/test_hooks.py` are clean.

import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from asf.m5_shared.memory.device_budget import DeviceSnapshot, load_memory_config, plan_device
from asf.m5_shared.memory.hooks import MemoryHooks
from asf.m5_shared.memory.store import MemoryRecord


@pytest.fixture
def hooks(tmp_path: Path, fake_paths: Any) -> MemoryHooks:
    _ = fake_paths
    snap = DeviceSnapshot(ram_total_mb=16_000, ram_free_mb=8_000, cpu_physical=4, cpu_logical=8, disk_free_mb=50_000, vram_total_mb=6_000, vram_free_mb=5_800)
    return MemoryHooks.open(tmp_path, plan=plan_device(snap, load_memory_config()))


def _spec(task: str = "t1") -> Any:
    return SimpleNamespace(task_id=task, goal="implement greet that returns a greeting", allowed_files=["src/greet.py"], capsules=[], context_budget_tokens=8192)


def test_the_memory_database_lives_in_the_project_factory_folder(hooks: MemoryHooks, tmp_path: Path) -> None:
    assert (tmp_path / ".factory" / "memory.db").exists()
    assert hooks.plan is not None and all(cap > 0 for cap in hooks.store.caps.values())


def test_a_failure_then_a_pass_leaves_an_episode_a_lesson_and_session_notes(hooks: MemoryHooks) -> None:
    spec = _spec()
    hooks.after_attempt(spec, "r1", 1, hooks.context_for(spec, "r1"), SimpleNamespace(failure_class="LOCAL_BUG"))
    routed = hooks.context_for(spec, "r1")
    assert any(d.ref.startswith("episodic:") for d in routed.included)  # the failure is shown to the next attempt
    hooks.after_attempt(spec, "r1", 2, routed, None)
    titles = [r.title for r in hooks.store.iter_records(["episodic"])]
    assert "LOCAL_BUG on src/greet.py" in titles and "lesson: LOCAL_BUG on src/greet.py" in titles
    assert hooks.store.stats()["session"] == 2
    hooks.after_run("r1", "DONE")
    assert hooks.store.stats()["session"] == 0


def test_a_lesson_from_two_runs_reaches_the_playbook(hooks: MemoryHooks) -> None:
    for run in ("r1", "r2"):
        spec = _spec()
        hooks.after_attempt(spec, run, 1, hooks.context_for(spec, run), SimpleNamespace(failure_class="LOCAL_BUG"))
        hooks.after_attempt(spec, run, 2, hooks.context_for(spec, run), None)
        hooks.after_run(run, "DONE")
    assert hooks.store.stats()["procedural"] == 1


def test_memory_failures_never_break_an_attempt(hooks: MemoryHooks) -> None:
    hooks.store.store_broken = True  # type: ignore[attr-defined]
    hooks.router.assemble = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[method-assign]
    assert hooks.context_for(_spec(), "r1").items == []
    hooks.after_attempt(SimpleNamespace(task_id="x", goal="g", allowed_files=[]), "r1", 1, hooks.context_for(_spec(), "r1"), object())


def test_the_store_is_safe_to_share_between_threads(hooks: MemoryHooks) -> None:
    def write(i: int) -> None:
        for j in range(20):
            hooks.store.remember(MemoryRecord(layer="semantic", title=f"fact {i}-{j}", text="parallel write"))

    threads = [threading.Thread(target=write, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert hooks.store.stats()["semantic"] == 80
