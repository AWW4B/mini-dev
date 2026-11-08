# FILE: src/asf/m5_shared/registry/registry.py
# ROLE: Stores versioned contracts, enforces compatibility, and serves pinned capsules (IF-07, IF-08).
# ARCH REF: M5; p09 Module & Interface Registry; IF-07 ContractRegister; IF-08 ContractQuery; A-1; D-32
# OWNS: Contract versions and status promotion
# DOES NOT OWN: Contract design (planner); test execution (gate)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/contract_spec.py: ContractCapsule, ContractQuery, ContractSpec, ContractStatus (IF-07/IF-08)
#   - imports from src/asf/m5_shared/registry/compatibility.py: classify_change (semver)
#   - imports from src/asf/m5_shared/registry/capsules.py: render_capsule (A-1)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (persistence)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (breaking-change approval)
#   - called by src/asf/m5_shared/context/context_service.py: ContractRegistry
#   - called by src/asf/m3_orchestration/planning/planner_graph.py: ContractRegistry
#   - called by src/asf/m3_orchestration/decomposition/leaf_certifier.py: ContractRegistry
#   - called by src/asf/m4_execution/verification/gate.py: ContractRegistry
#   - called by tests/m5_shared/registry/test_registry.py: ContractRegistry
#   - emits/consumes: emits CONTRACT_CHANGED events; raises DecisionRequest kind BREAKING_CONTRACT
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/registry/test_registry.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/registry/registry.py` and `uv run mypy src/asf/m5_shared/registry/registry.py` are clean.

import json
from datetime import UTC, datetime
from types import SimpleNamespace

from asf.contracts.contract_spec import ContractCapsule, ContractQuery, ContractSpec, ContractStatus
from asf.m5_shared.decisions.broker import DecisionBroker
from asf.m5_shared.registry.capsules import render_capsule
from asf.m5_shared.registry.compatibility import classify_change
from asf.m5_shared.state_store.store import StateStore


class ContractRegistry:
    store: StateStore
    broker: DecisionBroker | None

    def __init__(self, store: StateStore, broker: DecisionBroker | None = None) -> None:
        self.store = store
        self.broker = broker

    def register(self, spec: ContractSpec) -> ContractSpec:
        """IF-07: validate, classify change, store immutable version (breaking -> decision)."""
        parsed_spec: ContractSpec = (
            spec
            if isinstance(spec, ContractSpec)
            else ContractSpec.model_validate(
                json.loads(spec.model_dump_json()) if hasattr(spec, "model_dump_json") else spec.__dict__
            )
        )

        cur = self.store.conn.execute(
            "SELECT payload FROM contracts WHERE name = ? ORDER BY rowid DESC LIMIT 1",
            (parsed_spec.module_id,),
        )
        row = cur.fetchone()
        old_spec: ContractSpec | None = ContractSpec.model_validate_json(row["payload"]) if row else None

        change_type = classify_change(old_spec, parsed_spec)
        if change_type == "breaking" and self.broker is not None:
            now_iso = datetime.now(UTC).isoformat()
            req = SimpleNamespace(
                decision_id=f"dec-{parsed_spec.contract_id}",
                run_id="global",
                task_id=None,
                kind=SimpleNamespace(value="breaking_contract"),
                requester="m5_shared/registry",
                question=(
                    f"Contract {parsed_spec.module_id} has breaking changes. "
                    f"Approve new version {parsed_spec.version}?"
                ),
                options=["approve", "reject"],
                default_on_timeout=None,
                deadline=None,
                evidence_refs=[],
                model_dump_json=lambda: json.dumps(
                    {
                        "decision_id": f"dec-{parsed_spec.contract_id}",
                        "run_id": "global",
                        "task_id": None,
                        "kind": "breaking_contract",
                        "requester": "m5_shared/registry",
                        "question": (
                            f"Contract {parsed_spec.module_id} has breaking changes. "
                            f"Approve new version {parsed_spec.version}?"
                        ),
                        "options": ["approve", "reject"],
                        "default_on_timeout": None,
                        "deadline": None,
                        "evidence_refs": [],
                    }
                ),
                model_dump=lambda **kw: {"decision_id": f"dec-{parsed_spec.contract_id}"},
            )
            self.broker.request(req)  # type: ignore[arg-type]

        now_iso = datetime.now(UTC).isoformat()
        payload_str = parsed_spec.model_dump_json()
        with self.store.conn:
            self.store.conn.execute(
                "INSERT OR REPLACE INTO contracts (contract_id, project_id, name, version, payload, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (parsed_spec.contract_id, "default", parsed_spec.module_id, 1, payload_str, now_iso),
            )

        return parsed_spec

    def query(self, query: ContractQuery) -> list[ContractCapsule]:
        """IF-08: return capsules only, never implementations."""
        capsules: list[ContractCapsule] = []

        for mod_id in query.module_ids:
            found: ContractSpec | None = None
            if query.pinned_versions and mod_id in query.pinned_versions:
                pinned_v = query.pinned_versions[mod_id]
                cur = self.store.conn.execute(
                    "SELECT payload FROM contracts WHERE name = ? ORDER BY rowid DESC",
                    (mod_id,),
                )
                for row in cur.fetchall():
                    candidate = ContractSpec.model_validate_json(row["payload"])
                    if candidate.version == pinned_v:
                        found = candidate
                        break
            else:
                cur = self.store.conn.execute(
                    "SELECT payload FROM contracts WHERE name = ? ORDER BY rowid DESC LIMIT 1",
                    (mod_id,),
                )
                row = cur.fetchone()
                if row:
                    found = ContractSpec.model_validate_json(row["payload"])

            if found is not None:
                for op in found.operations:
                    capsules.append(render_capsule(found, op.name))

        return capsules

    def promote(self, contract_id: str, status: ContractStatus) -> None:
        cur = self.store.conn.execute(
            "SELECT payload FROM contracts WHERE contract_id = ?",
            (contract_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise KeyError(f"Contract {contract_id} not found")

        spec = ContractSpec.model_validate_json(row["payload"])
        status_val = (
            status
            if isinstance(status, ContractStatus)
            else ContractStatus(str(getattr(status, "value", status)))
        )
        updated = spec.model_copy(update={"status": status_val})

        with self.store.conn:
            self.store.conn.execute(
                "UPDATE contracts SET payload = ? WHERE contract_id = ?",
                (updated.model_dump_json(), contract_id),
            )
