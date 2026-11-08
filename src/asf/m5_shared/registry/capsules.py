# FILE: src/asf/m5_shared/registry/capsules.py
# ROLE: Renders a contract operation as a 3-5 line capsule (A-1).
# ARCH REF: M5; p09; A-1; IF-08
# OWNS: Capsule rendering
# DOES NOT OWN: Choosing which capsules a task needs (registry.query)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/contract_spec.py: ContractSpec, ContractCapsule (A-1)
#   - called by src/asf/m5_shared/registry/registry.py: render_capsule
#   - called by tests/m5_shared/registry/test_capsules.py: render_capsule
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Lines: signature; parameter meanings; returns; errors; one example. Never include implementation code.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/registry/test_capsules.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/registry/capsules.py` and `uv run mypy src/asf/m5_shared/registry/capsules.py` are clean.

from asf.contracts.contract_spec import ContractCapsule, ContractSpec


def render_capsule(spec: ContractSpec, operation: str) -> ContractCapsule:
    op = next((o for o in spec.operations if o.name == operation), None)
    if op is None:
        raise KeyError(f"Operation '{operation}' not found in contract {spec.module_id}@{spec.version}")

    params_str = ", ".join(f"{k}: {v}" for k, v in op.params.items()) if op.params else "none"
    errors_str = ", ".join(op.errors) if op.errors else "none"
    example_str = op.example if op.example else "none"

    lines = [
        f"SIG: {op.signature}",
        f"PARAMS: {params_str}",
        f"RETURNS: {op.returns}",
        f"ERRORS: {errors_str}",
        f"EX: {example_str}",
    ]

    return ContractCapsule(
        module_id=spec.module_id,
        version=spec.version,
        operation=operation,
        lines=lines,
    )
