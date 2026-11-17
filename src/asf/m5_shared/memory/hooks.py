# FILE: src/asf/m5_shared/memory/hooks.py
# ROLE: The memory workflow around attempts and runs: read memory before an attempt, record outcomes after it, consolidate after a run.
# ARCH REF: M5; p12 Context & Memory Service; docs/architecture/MEMORY_ARCHITECTURE.md
# OWNS: When memory is read and written
# DOES NOT OWN: Selection (router.py), storage (store.py)
# CONNECTS TO (external boundaries only):
#   - called by tests/m5_shared/memory/test_hooks.py: MemoryHooks
#   - called by src/asf/m3_orchestration/run_graph.py: MemoryHooks
#   - imports from src/asf/m5_shared/memory/budgets.py: budgets_for (the coder's layer budgets)
#   - imports from src/asf/m5_shared/memory/device_budget.py: DevicePlan, load_memory_config, plan_device, probe_device (this machine's limits)
#   - imports from src/asf/m5_shared/memory/router.py: MemoryRouter, RoutedMemory (selection)
#   - imports from src/asf/m5_shared/memory/store.py: MemoryRecord, MemoryStore, open_memory_store, row_caps (the memory database)
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/memory/test_hooks.py pass on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/memory/hooks.py` and `uv run mypy src/asf/m5_shared/memory/hooks.py` are clean.

import logging
from pathlib import Path
from typing import Any

from asf.m5_shared.memory.budgets import budgets_for
from asf.m5_shared.memory.device_budget import DevicePlan, load_memory_config, plan_device, probe_device
from asf.m5_shared.memory.router import MemoryRouter, RoutedMemory
from asf.m5_shared.memory.store import MemoryRecord, MemoryStore, open_memory_store, row_caps

logger = logging.getLogger(__name__)


def _query(spec: Any) -> str:
    capsules = " ".join(f"{c.module_id} {c.operation}" for c in getattr(spec, "capsules", []))
    return f"{spec.goal} {' '.join(spec.allowed_files)} {capsules}"


class MemoryHooks:
    """The memory workflow around the orchestrator's work units. Every call is best-effort: memory must never fail a run.

    before an attempt   -> context_for(): the router picks procedural, session, semantic and episodic memory for T2
    after an attempt    -> after_attempt(): included memory is credited or blamed; a failure becomes an episode; a pass
                           after a failure becomes a lesson ("when X failed like this, what worked"); a session note is kept
    after the run       -> after_run(): session notes fold into one episode; lessons seen in enough runs are promoted
    """

    def __init__(self, store: MemoryStore, router: MemoryRouter, config: dict[str, Any], plan: DevicePlan | None = None) -> None:
        self.store = store
        self.router = router
        self.config = config
        self.plan = plan

    @classmethod
    def open(cls, project_root: Path, *, gateway: Any = None, skills: Any = None, plan: DevicePlan | None = None) -> "MemoryHooks":
        config = load_memory_config(project_root)
        plan = plan or plan_device(probe_device(), config)
        store = open_memory_store(
            project_root / ".factory" / "memory.db", caps=row_caps(plan.disk_cap_mb, dict(config.get("retention", {}))),
            retention=dict(config.get("retention", {})), cache_mb=plan.sqlite_cache_mb,
        )
        return cls(store, MemoryRouter(store, config, skills=skills, gateway=gateway), config, plan)

    def context_for(self, spec: Any, run_id: str | None, role: str = "T2") -> RoutedMemory:
        try:
            budgets = budgets_for(role, int(spec.context_budget_tokens), self.config)
            return self.router.assemble(role, _query(spec), budgets, run_id=run_id)
        except Exception:  # noqa: BLE001 - a memory failure degrades to "no memory", it never blocks the attempt
            logger.warning("memory retrieval failed for %s; continuing without memory", getattr(spec, "task_id", "?"), exc_info=True)
            return RoutedMemory()

    def after_attempt(self, spec: Any, run_id: str | None, attempt_no: int, routed: RoutedMemory, verdict: Any) -> None:
        task_id = str(spec.task_id)
        passed = verdict is None
        failure = None if passed else str(getattr(verdict, "failure_class", "UNKNOWN"))
        failure = getattr(failure, "value", failure)
        files = ", ".join(spec.allowed_files)
        try:
            self.store.mark_outcome(routed.record_ids, helpful=passed)
            if run_id:
                note = "verified" if passed else f"failed with {failure}"
                self.store.remember(
                    MemoryRecord(layer="session", scope=f"run:{run_id}", topic=f"task/{task_id}", title=f"{task_id} attempt {attempt_no} {note}",
                                 text=f"{spec.goal} ({files})", run_id=run_id, task_id=task_id)
                )
            if not passed:
                self.store.remember(
                    MemoryRecord(layer="episodic", topic=f"failure/{failure}", title=f"{failure} on {files}",
                                 text=f"Task: {spec.goal}. Attempt {attempt_no} failed the gate with {failure}.", tags=["failure", str(failure)],
                                 run_id=run_id, task_id=task_id)
                )
            elif attempt_no > 1:
                earlier = [r for r in self.store.search(spec.goal, ["episodic"], limit=10) if r.task_id == task_id and "failure" in r.tags]
                for record in earlier[:1]:
                    self.store.remember(
                        MemoryRecord(layer="episodic", topic=record.topic, title=f"lesson: {record.title}",
                                     text=f"{record.text} A later attempt passed; the change touched {files}.", tags=["lesson", *record.tags[1:]],
                                     run_id=run_id, task_id=task_id)
                    )
        except Exception:  # noqa: BLE001 - recording is best-effort; the gate verdict stands regardless
            logger.warning("could not record memory for %s attempt %s", task_id, attempt_no, exc_info=True)

    def after_run(self, run_id: str, status: str) -> None:
        try:
            self.store.end_session(run_id, status)
            self.store.promote()
        except Exception:  # noqa: BLE001 - consolidation is best-effort
            logger.warning("could not consolidate memory for run %s", run_id, exc_info=True)
