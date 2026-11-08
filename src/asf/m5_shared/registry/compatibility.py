# FILE: src/asf/m5_shared/registry/compatibility.py
# ROLE: Classifies a contract change as patch, minor or breaking (semver rules).
# ARCH REF: M5; p09 compatibility check
# OWNS: Change classification
# DOES NOT OWN: Approval of breaking changes (broker)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/contract_spec.py: ContractSpec (IF-07)
#   - called by src/asf/m5_shared/registry/registry.py: classify_change
#   - called by tests/m5_shared/registry/test_compatibility.py: classify_change
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/registry/test_compatibility.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/registry/compatibility.py` and `uv run mypy src/asf/m5_shared/registry/compatibility.py` are clean.

from asf.contracts.contract_spec import ContractSpec


def classify_change(old: ContractSpec | None, new: ContractSpec) -> str:
    """Return 'new' | 'patch' | 'minor' | 'breaking'."""
    if old is None:
        return "new"

    old_ops = {op.name: op for op in old.operations}
    new_ops = {op.name: op for op in new.operations}

    # 1. Breaking check: any old operation removed or altered?
    for name, old_op in old_ops.items():
        if name not in new_ops:
            return "breaking"
        new_op = new_ops[name]
        if old_op.signature != new_op.signature or old_op.returns != new_op.returns:
            return "breaking"

    # 2. Breaking check: any old schema removed or changed?
    for schema_name, old_schema in old.data_schemas.items():
        if schema_name not in new.data_schemas:
            return "breaking"
        if new.data_schemas[schema_name] != old_schema:
            return "breaking"

    # 3. Breaking check: any old invariant removed?
    new_invariants_set = set(new.invariants)
    for inv in old.invariants:
        if inv not in new_invariants_set:
            return "breaking"

    # 4. Minor check: any new operation, schema, or invariant added?
    if len(new_ops) > len(old_ops):
        return "minor"
    if len(new.data_schemas) > len(old.data_schemas):
        return "minor"
    if len(new.invariants) > len(old.invariants):
        return "minor"

    # 5. Otherwise, patch
    return "patch"
