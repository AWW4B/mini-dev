# FILE: src/asf/m4_execution/scheduler.py
# ROLE: Task Scheduler: dependency-, resource- and model-aware dispatch with slot leases; plain Python, no LangGraph.
# ARCH REF: M4; p07 Task Scheduler; IF-09; IF-10; IF-13; IF-06; IF-20; IF-21 Requeue; D-06
# OWNS: Ready set, ranking, lease acquisition, dispatch, requeue
# DOES NOT OWN: Running attempts (worker_graph)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tasks.py: LeafTaskSpec (IF-09)
#   - imports from src/asf/contracts/outcomes.py: Requeue, TaskOutcome (IF-21/IF-10)
#   - imports from src/asf/contracts/control.py: CancelSignal (IF-06)
#   - imports from src/asf/contracts/metrics.py: ResourceAdvisory (IF-20)
#   - imports from src/asf/m5_shared/runtime/local_runtime.py: LocalRuntime (IF-13)
#   - imports from src/asf/m4_execution/worker/worker_graph.py: run_attempt (dispatch)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (IF-16 state)
#   - imports from src/asf/contracts/models.py: SlotLease, SlotLeaseRequest (IF-13)
#   - called by src/asf/m3_orchestration/run_control.py: TaskScheduler
#   - called by src/asf/m3_orchestration/decomposition/decomposition_graph.py: TaskScheduler
#   - called by src/asf/m4_execution/integration/integrator.py: TaskScheduler
#   - called by tests/m4_execution/test_scheduler.py: MAX_INFRA_RETRIES, TaskScheduler
#   - emits/consumes: emits STATE_CHANGED and HANDOFF_SENT (scheduler -> worker, causation = the READY event)
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Upsert by idempotency key; hold BLOCKED until deps VERIFIED; wait for SLOT_FREE without busy polling.
#   6. Dispatch cap = max_slots from the runtime.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m4_execution/test_scheduler.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m4_execution/scheduler.py` and `uv run mypy src/asf/m4_execution/scheduler.py` are clean.

import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from asf.contracts.control import CancelSignal
from asf.contracts.metrics import ResourceAdvisory
from asf.contracts.models import SlotLease, SlotLeaseRequest
from asf.contracts.outcomes import Requeue, TaskOutcome
from asf.contracts.tasks import LeafTaskSpec
from asf.m5_shared.runtime.local_runtime import LocalRuntime
from asf.m5_shared.state_store.store import StateStore

logger = logging.getLogger(__name__)

MAX_INFRA_RETRIES = 3
_DONE_STATES = ("VERIFIED", "INTEGRATED")

AttemptRunner = Callable[[LeafTaskSpec, SlotLease, int], Requeue | TaskOutcome | None]
Sink = Callable[[str, dict[str, Any]], None]
OutcomeSink = Callable[[TaskOutcome], None]


class TaskScheduler:
    """Dependency-, resource- and model-aware dispatch with slot leases. Plain Python; thread-safe.

    ``attempt_runner(spec, lease, attempt_no)`` runs one worker attempt plus the gate and returns ``None`` (verified),
    a ``Requeue`` (fixable failure) or a ``TaskOutcome`` (non-local failure). Outcomes for M3 go to ``outcome_sink``;
    STATE_CHANGED / HANDOFF_SENT narrative payloads go to ``event_sink``.
    """

    def __init__(
        self,
        runtime: LocalRuntime | None = None,
        store: StateStore | None = None,
        attempt_runner: AttemptRunner | None = None,
        outcome_sink: OutcomeSink | None = None,
        event_sink: Sink | None = None,
        ctx_tokens: int = 8192,
        lease_ttl_s: int = 600,
    ) -> None:
        self._runtime = runtime
        self._store = store
        self._runner = attempt_runner
        self._outcome_sink = outcome_sink
        self._event_sink = event_sink
        self._ctx_tokens = ctx_tokens
        self._lease_ttl_s = lease_ttl_s

        self._lock = threading.RLock()
        self._specs: dict[str, LeafTaskSpec] = {}
        self._order: dict[str, int] = {}  # enqueue order = age
        self._state: dict[str, str] = {}
        self._attempts: dict[str, int] = {}
        self._infra_retries: dict[str, int] = {}
        self._evidence: dict[str, str] = {}
        self._leases: dict[str, SlotLease] = {}
        self._verified: set[str] = set()
        self._deps: dict[str, set[str]] = {}
        self._advisory_cap: int | None = None
        self._paused = False
        self._last_model: str | None = None  # model affinity: prefer tasks for the model that is already loaded
        self._futures: dict[str, Future[None]] = {}
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="asf-attempt")

    # -- observation (also what the tests and the CLI read) ------------------------------------------------------

    def state_of(self, task_id: str) -> str | None:
        with self._lock:
            return self._state.get(task_id)

    def attempts_of(self, task_id: str) -> int:
        with self._lock:
            return self._attempts.get(task_id, 0)

    def latest_evidence(self, task_id: str) -> str | None:
        """Only the newest failure evidence is kept (older attempts are summarised away)."""
        with self._lock:
            return self._evidence.get(task_id)

    def dispatch_cap(self) -> int:
        slots = self._runtime.max_slots() if self._runtime is not None else 1
        return slots if self._advisory_cap is None else max(1, min(slots, self._advisory_cap))

    def wait_idle(self, timeout_s: float = 30.0) -> bool:
        """Block until every running attempt has finished (used by tests and by graceful shutdown)."""
        with self._lock:
            futures = list(self._futures.values())
        for future in futures:
            try:
                future.result(timeout=timeout_s)
            except TimeoutError:
                return False
        return True

    def close(self) -> None:
        self._pool.shutdown(wait=True)

    # -- inputs ---------------------------------------------------------------------------------------------------

    def enqueue(self, spec: LeafTaskSpec) -> None:
        """IF-09. Upsert by task id (the idempotency key): a duplicate enqueue changes nothing."""
        task_id = str(spec.task_id)
        with self._lock:
            if task_id in self._specs:
                return
            self._specs[task_id] = spec
            self._order[task_id] = len(self._order)
            self._deps[task_id] = self._lookup_deps(task_id)
            self._set_state(task_id, "BLOCKED" if not self._deps_done(task_id) else "READY")

    def mark_verified(self, task_id: str) -> None:
        """IF-17 TaskVerified / Integrated for a dependency: re-check the tasks that were waiting for it."""
        with self._lock:
            self._verified.add(task_id)
            if task_id in self._state and self._state[task_id] not in ("CANCELLED",):
                self._set_state(task_id, "VERIFIED")
            self._refresh_blocked(use_store=True)

    def requeue(self, item: Requeue) -> None:
        """IF-21: READY again if attempts < max_attempts, else TaskOutcome ESCALATED (IF-10)."""
        task_id = str(item.task_id)
        with self._lock:
            spec = self._specs.get(task_id)
            if spec is None:
                logger.warning("requeue for unknown task %s ignored", task_id)
                return
            attempts = self._attempts.get(task_id, 0)
            self._evidence[task_id] = item.evidence_ref
            if attempts < spec.max_attempts:
                self._set_state(task_id, "READY")
                return
            self._set_state(task_id, "ESCALATED")
            outcome = TaskOutcome.model_validate(
                {"task_id": task_id, "failure_class": "ESCALATED", "evidence_ref": item.evidence_ref, "attempts": attempts}
            )
        self._deliver(outcome)

    def on_cancel(self, signal: CancelSignal) -> None:
        """IF-06: pause suspends, resume re-evaluates, abort / cancel_task cancel; leases in scope are revoked."""
        command = getattr(signal.command, "value", str(signal.command))
        with self._lock:
            if command == "pause":
                self._paused = True
                for task_id, state in self._state.items():
                    if state in ("READY", "BLOCKED"):
                        self._set_state(task_id, "SUSPENDED")
                return
            if command == "resume":
                self._paused = False
                for task_id, state in list(self._state.items()):
                    if state == "SUSPENDED":
                        self._set_state(task_id, "READY" if self._deps_done(task_id) else "BLOCKED")
                return
            targets = [str(signal.task_id)] if command == "cancel_task" and signal.task_id else list(self._state)
            for task_id in targets:
                if self._state.get(task_id) in ("VERIFIED", "INTEGRATED", "ESCALATED"):
                    continue
                if task_id in self._state:
                    self._set_state(task_id, "CANCELLED")
                self._revoke_lease(task_id)

    def on_advisory(self, advisory: ResourceAdvisory) -> None:
        """IF-20: the dispatch cap follows max_slots (1 or 2); no cap clears the advisory."""
        with self._lock:
            self._advisory_cap = advisory.max_slots

    # -- dispatch -------------------------------------------------------------------------------------------------

    def dispatch_ready(self) -> int:
        """Start as many READY attempts as there are free slots; return how many were started.

        Call again when a slot is freed (SLOT_FREE) or a task becomes READY; there is no polling loop here.
        """
        if self._runner is None or self._runtime is None:
            raise RuntimeError("TaskScheduler needs a LocalRuntime and an attempt_runner to dispatch")
        started = 0
        with self._lock:
            if self._paused:
                return 0
            self._refresh_blocked(use_store=True)
            for task_id in self._ranked_ready():
                if len(self._leases) >= self.dispatch_cap():
                    break
                spec = self._specs[task_id]
                lease = self._runtime.acquire(
                    SlotLeaseRequest.model_validate(
                        {"model_id": spec.model_role, "ctx_tokens": self._ctx_tokens, "ttl_s": self._lease_ttl_s, "priority": 0}
                    )
                )
                if lease is None:
                    break  # no free slot: wait for SLOT_FREE
                attempt_no = self._attempts.get(task_id, 0) + 1
                self._attempts[task_id] = attempt_no
                self._leases[task_id] = lease
                self._last_model = spec.model_role
                self._set_state(task_id, "RUNNING")
                self._emit("HANDOFF_SENT", {"task_id": task_id, "to_role": "worker", "attempt_no": attempt_no, "lease_id": str(lease.lease_id)})
                self._futures[task_id] = self._pool.submit(self._run, task_id, spec, lease, attempt_no)
                started += 1
        return started

    # -- internals ------------------------------------------------------------------------------------------------

    def _run(self, task_id: str, spec: LeafTaskSpec, lease: SlotLease, attempt_no: int) -> None:
        result: Requeue | TaskOutcome | None = None
        infra_failure: str | None = None
        assert self._runner is not None
        try:
            result = self._runner(spec, lease, attempt_no)
        except Exception as err:  # noqa: BLE001 - the attempt runner raises worker, context and infrastructure errors alike
            name = type(err).__name__
            if name == "ContextOverflow":
                result = self._outcome(task_id, "CONTEXT_OVERFLOW", str(err), attempt_no)
            elif name == "WorkerBlocked":
                text = str(err)
                failure = "SPEC_TOO_LARGE" if "SPEC_TOO_LARGE" in text else "CONTEXT_OVERFLOW" if "CONTEXT_OVERFLOW" in text else "CONTRACT_GAP"
                result = self._outcome(task_id, failure, text, attempt_no)
            else:
                logger.warning("attempt %d of task %s failed for an infrastructure reason", attempt_no, task_id, exc_info=True)
                infra_failure = f"{name}: {err}"
        finally:
            with self._lock:
                self._revoke_lease(task_id)

        if infra_failure is not None:
            self._handle_infra_failure(task_id, infra_failure, attempt_no)
        elif result is None:
            with self._lock:
                self._verified.add(task_id)
                self._set_state(task_id, "VERIFIED")
                self._refresh_blocked(use_store=False)  # the caller's next dispatch_ready() re-checks against the store
        elif isinstance(result, Requeue):
            self.requeue(result)
        else:
            with self._lock:
                self._set_state(task_id, "ESCALATED")
            self._deliver(result)

    def _handle_infra_failure(self, task_id: str, reason: str, attempt_no: int) -> None:
        """An infrastructure failure does not cost an attempt; after MAX_INFRA_RETRIES it is reported instead."""
        with self._lock:
            self._attempts[task_id] = max(0, self._attempts.get(task_id, 1) - 1)
            retries = self._infra_retries.get(task_id, 0) + 1
            self._infra_retries[task_id] = retries
            if retries <= MAX_INFRA_RETRIES:
                self._evidence[task_id] = reason
                self._set_state(task_id, "READY")
                return
            self._set_state(task_id, "ESCALATED")
        self._deliver(self._outcome(task_id, "ENV_INFRA", reason, attempt_no))

    @staticmethod
    def _outcome(task_id: str, failure_class: str, evidence: str, attempts: int) -> TaskOutcome:
        return TaskOutcome.model_validate({"task_id": task_id, "failure_class": failure_class, "evidence_ref": evidence[:2000], "attempts": attempts})

    def _deliver(self, outcome: TaskOutcome) -> None:
        self._emit("TASK_OUTCOME", {"task_id": str(outcome.task_id), "failure_class": outcome.failure_class.value})
        if self._outcome_sink is not None:
            self._outcome_sink(outcome)

    def _revoke_lease(self, task_id: str) -> None:
        lease = self._leases.pop(task_id, None)
        if lease is not None and self._runtime is not None:
            self._runtime.release(str(lease.lease_id))

    def _set_state(self, task_id: str, state: str) -> None:
        previous = self._state.get(task_id)
        self._state[task_id] = state
        if previous != state:
            self._emit("STATE_CHANGED", {"task_id": task_id, "from": previous, "to": state})

    def _emit(self, kind: str, payload: dict[str, Any]) -> None:
        if self._event_sink is not None:
            self._event_sink(kind, payload)

    def _lookup_deps(self, task_id: str) -> set[str]:
        if self._store is None:
            return set()
        try:
            return {str(d) for d in self._store.get_task(task_id).deps}
        except KeyError:
            return set()  # not in the store: the caller only wants it ordered, not blocked

    def _refresh_blocked(self, use_store: bool) -> None:
        for waiting, state in list(self._state.items()):
            if state == "BLOCKED" and self._deps_done(waiting, use_store):
                self._set_state(waiting, "READY")

    def _deps_done(self, task_id: str, use_store: bool = True) -> bool:
        """Dependencies are done when verified here or recorded VERIFIED/INTEGRATED in the store.

        The store's SQLite connection belongs to the thread that opened it, so attempt threads pass use_store=False.
        """
        for dep in self._deps.get(task_id, set()):
            if dep in self._verified:
                continue
            if use_store and self._store is not None:
                row = self._store.conn.execute("SELECT state FROM tasks WHERE task_id = ?", (dep,)).fetchone()
                if row is not None and row["state"] in _DONE_STATES:
                    continue
            return False
        return True

    def _ranked_ready(self) -> list[str]:
        """Critical path first: priority, then how many tasks it unblocks, then age."""
        ready = [t for t, s in self._state.items() if s == "READY"]
        unblocks = {t: sum(1 for deps in self._deps.values() if t in deps) for t in ready}
        return sorted(ready, key=lambda t: (-unblocks[t], 0 if self._specs[t].model_role == self._last_model else 1, self._order[t]))
