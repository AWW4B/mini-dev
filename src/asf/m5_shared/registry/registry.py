# FILE: src/asf/m5_shared/registry/registry.py
# ROLE: Stores versioned contracts, enforces compatibility, and serves pinned capsules (IF-07, IF-08).
# ARCH REF: M5; p09 Module & Interface Registry; IF-07 ContractRegister; IF-08 ContractQuery; A-1; D-32
# OWNS: Contract versions and status promotion
# DOES NOT OWN: Contract design (planner); test execution (gate)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/contract_spec.py: ContractSpec, ContractCapsule, ContractQuery, ContractStatus (IF-07/IF-08)
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

from asf.contracts.contract_spec import ContractCapsule, ContractQuery, ContractSpec, ContractStatus


class ContractRegistry:
    def register(self, spec: ContractSpec) -> ContractSpec:
        """IF-07: validate, classify change, store immutable version (breaking -> decision)."""
        raise NotImplementedError

    def query(self, query: ContractQuery) -> list[ContractCapsule]:
        """IF-08: return capsules only, never implementations."""
        raise NotImplementedError

    def promote(self, contract_id: str, status: ContractStatus) -> None:
        raise NotImplementedError
