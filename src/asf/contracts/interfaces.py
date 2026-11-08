# FILE: src/asf/contracts/interfaces.py
# ROLE: Catalog of every cross-module interface IF-01..IF-24 with its producer, consumer and payload model.
# ARCH REF: p15 interface catalog; IF-01; IF-02; IF-03; IF-04; IF-05; IF-06; IF-07; IF-07a; IF-08; IF-09; IF-10; IF-10b; IF-10c; IF-11; IF-12; IF-13; IF-14; IF-15; IF-16; IF-17; IF-18; IF-19; IF-20; IF-21; IF-23; IF-24
# OWNS: The single machine-readable list of interface IDs used by tests and scripts/check_headers.py
# DOES NOT OWN: The payload models (other contract files)
# CONNECTS TO (external boundaries only):
#   - called by tests/contracts/test_interfaces.py: InterfaceInfo, INTERFACES
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. This file is declarations only: Pydantic models, enums and type aliases. Add field validators only where the docstring of a field states a constraint.
#   6. Every model must round-trip through model_dump_json() / model_validate_json() unchanged; the JSON Schema exported from these models is the published contract (D-39: no hand-written JSON).
#   7. Changing a field name or type is a contract change: stop and report instead.
#   8. Keep INTERFACES in sync with drawio page 15; adding an interface requires the drawio and every affected header to change first.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; business logic; I/O; imports from asf.m1-m5 packages, asf.cli, asf.web or asf.platform
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/contracts/test_interfaces.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/contracts/interfaces.py` and `uv run mypy src/asf/contracts/interfaces.py` are clean.

from pydantic import BaseModel


class InterfaceInfo(BaseModel):
    if_id: str
    name: str
    producer: str
    consumer: str
    payload_model: str
    kind: str


INTERFACES: dict[str, InterfaceInfo] = {
    i.if_id: i for i in [
        InterfaceInfo(if_id="IF-01", name="SubmitRequest", producer="M1 cli", consumer="M2 intake_router", payload_model="asf.contracts.requests.SubmitRequest", kind="command"),
        InterfaceInfo(if_id="IF-02", name="StructuredRequest", producer="M2 request_understanding", consumer="M3 run_graph", payload_model="asf.contracts.requests.StructuredRequest", kind="command"),
        InterfaceInfo(if_id="IF-03", name="DecisionRequest", producer="any", consumer="M5 decisions.broker", payload_model="asf.contracts.decisions.DecisionRequest", kind="command+event"),
        InterfaceInfo(if_id="IF-04", name="DecisionResolved", producer="M1 inbox", consumer="requester", payload_model="asf.contracts.decisions.DecisionResolved", kind="event"),
        InterfaceInfo(if_id="IF-05", name="RunControl", producer="M1 cli", consumer="M3 run_control", payload_model="asf.contracts.control.RunControl", kind="command"),
        InterfaceInfo(if_id="IF-06", name="CancelSignal", producer="M3 run_control", consumer="M2, M4, M5 runtime", payload_model="asf.contracts.control.CancelSignal", kind="event"),
        InterfaceInfo(if_id="IF-07", name="ContractRegister", producer="M3, M4", consumer="M5 registry", payload_model="asf.contracts.contract_spec.ContractSpec", kind="call"),
        InterfaceInfo(if_id="IF-07a", name="ApprovedPlan", producer="M3 planning", consumer="M3 decomposition", payload_model="asf.contracts.outcomes.ApprovedPlan", kind="internal"),
        InterfaceInfo(if_id="IF-08", name="ContractQuery", producer="M3, M4, M5 context", consumer="M5 registry", payload_model="asf.contracts.contract_spec.ContractQuery", kind="call"),
        InterfaceInfo(if_id="IF-09", name="ReadyTask", producer="M3 decomposition, M4 integration", consumer="M4 scheduler", payload_model="asf.contracts.tasks.LeafTaskSpec", kind="command"),
        InterfaceInfo(if_id="IF-10", name="TaskOutcome", producer="M4", consumer="M3", payload_model="asf.contracts.outcomes.TaskOutcome", kind="event"),
        InterfaceInfo(if_id="IF-10b", name="DecompositionReport", producer="M3 decomposition", consumer="M3 run_graph", payload_model="asf.contracts.outcomes.DecompositionReport", kind="event"),
        InterfaceInfo(if_id="IF-10c", name="RootIntegrated", producer="M4 integration", consumer="M3 run_graph", payload_model="asf.contracts.outcomes.RootIntegrated", kind="event"),
        InterfaceInfo(if_id="IF-11", name="ContextRequest", producer="M2, M3, M4", consumer="M5 context", payload_model="asf.contracts.context.ContextRequest", kind="call"),
        InterfaceInfo(if_id="IF-12", name="InferenceRequest", producer="M2, M3, M4", consumer="M5 gateway", payload_model="asf.contracts.models.InferenceRequest", kind="call"),
        InterfaceInfo(if_id="IF-13", name="SlotLease", producer="M4 scheduler", consumer="M5 runtime", payload_model="asf.contracts.models.SlotLeaseRequest", kind="call"),
        InterfaceInfo(if_id="IF-14", name="ToolInvocation", producer="M2, M3, M4", consumer="M5 tools.executor", payload_model="asf.contracts.tools.ToolInvocation", kind="call"),
        InterfaceInfo(if_id="IF-15", name="WorkspaceOps", producer="M2, M4", consumer="M5 workspace", payload_model="asf.contracts.workspace.WorkspaceOp", kind="call"),
        InterfaceInfo(if_id="IF-16", name="StateCommit", producer="all", consumer="M5 state_store", payload_model="asf.contracts.state.StateCommit", kind="call"),
        InterfaceInfo(if_id="IF-17", name="EventPublish", producer="all (outbox)", consumer="M5 events", payload_model="asf.contracts.events.EventEnvelope", kind="event"),
        InterfaceInfo(if_id="IF-18", name="EventSubscribe", producer="M5 events", consumer="M1 cli views, web viewer, M3, M4", payload_model="asf.contracts.events.EventEnvelope", kind="stream"),
        InterfaceInfo(if_id="IF-19", name="MetricsSnapshot", producer="M5 metrics", consumer="M1 dashboard", payload_model="asf.contracts.metrics.MetricsSnapshot", kind="stream"),
        InterfaceInfo(if_id="IF-20", name="ResourceAdvisory", producer="M5 metrics, runtime", consumer="M3, M4", payload_model="asf.contracts.metrics.ResourceAdvisory", kind="event"),
        InterfaceInfo(if_id="IF-21", name="ChangeSet / Requeue", producer="M4 worker, gate", consumer="M4 gate, scheduler", payload_model="asf.contracts.outcomes.ChangeSet", kind="internal"),
        InterfaceInfo(if_id="IF-23", name="SkillLookup", producer="M2, M3, M4", consumer="M5 tools.skills", payload_model="asf.contracts.tools.SkillManifest", kind="call"),
        InterfaceInfo(if_id="IF-24", name="HistoryQuery", producer="M1 cli", consumer="M5 state_store", payload_model="asf.contracts.history.HistoryQuery", kind="call"),
    ]
}
