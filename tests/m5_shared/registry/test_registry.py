# FILE: tests/m5_shared/registry/test_registry.py
# ROLE: Tests that prove src/asf/m5_shared/registry/registry.py meets its DONE WHEN conditions.
# ARCH REF: M5; p09 Module & Interface Registry; IF-07 ContractRegister; IF-08 ContractQuery; A-1; D-32; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/registry/registry.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/registry/registry.py: ContractRegistry (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/registry/test_registry.py` on Windows and Linux once src/asf/m5_shared/registry/registry.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/registry/test_registry.py` and `uv run mypy tests/m5_shared/registry/test_registry.py` are clean.

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from asf.m5_shared.registry.registry import ContractRegistry


def _create_contracts_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS contracts (
            contract_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            payload TEXT NOT NULL DEFAULT '{}',
            created_at TEXT
        );
        """
    )
    conn.commit()


def test_contract_registry_meets_contract(tmp_path: Path) -> None:
    """Prove ContractRegistry behaves as declared in src/asf/m5_shared/registry/registry.py."""
    db_file = tmp_path / "registry.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    _create_contracts_table(conn)

    decisions: list[Any] = []

    class FakeBroker:
        def request(self, req: Any) -> None:
            decisions.append(req)

    store = SimpleNamespace(conn=conn)
    broker = FakeBroker()
    registry = ContractRegistry(store=store, broker=broker)  # type: ignore[arg-type]

    op1 = {
        "name": "login",
        "signature": "login(user: str, secret: str) -> Token",
        "params": {"user": "name"},
        "returns": "Token",
        "errors": [],
        "example": 'login("alice", "pw")',
    }

    spec1 = {
        "contract_id": "auth-v1",
        "module_id": "auth",
        "version": "1.0.0",
        "status": "DRAFT",
        "operations": [op1],
        "data_schemas": {"Token": "token: str"},
        "invariants": [],
        "producer_task": None,
        "consumer_tasks": [],
        "contract_test_refs": [],
    }

    # 1. Register new contract
    registered = registry.register(SimpleNamespace(**spec1, model_dump_json=lambda: json.dumps(spec1)))  # type: ignore[arg-type]
    assert registered.module_id == "auth"
    assert len(decisions) == 0

    # 2. Query capsules
    q = SimpleNamespace(module_ids=["auth"], task_id=None, pinned_versions={})
    capsules = registry.query(q)  # type: ignore[arg-type]
    assert len(capsules) == 1
    assert capsules[0].module_id == "auth"
    assert capsules[0].operation == "login"
    assert 3 <= len(capsules[0].lines) <= 5

    # 3. Register breaking change: triggers broker request
    spec_break = dict(spec1)
    spec_break["contract_id"] = "auth-v2"
    spec_break["version"] = "2.0.0"
    spec_break["operations"] = []  # removed operation
    registry.register(SimpleNamespace(**spec_break, model_dump_json=lambda: json.dumps(spec_break)))  # type: ignore[arg-type]
    assert len(decisions) == 1

    # 4. Promote
    registry.promote("auth-v1", SimpleNamespace(value="VERIFIED"))  # type: ignore[arg-type]
    row = conn.execute("SELECT payload FROM contracts WHERE contract_id = 'auth-v1'").fetchone()
    assert row is not None
    data = json.loads(row["payload"])
    assert data["status"] == "VERIFIED"

    conn.close()
