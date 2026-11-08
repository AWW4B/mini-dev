# FILE: tests/m5_shared/tools/test_policy.py
# ROLE: Tests that prove src/asf/m5_shared/tools/policy.py meets its DONE WHEN conditions.
# ARCH REF: M5; p12; D-16; D-18 per-server policy; D-21; D-22; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/tools/policy.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/tools/policy.py: Verdict, PolicyVerdict, PolicyEngine (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/tools/test_policy.py` on Windows and Linux once src/asf/m5_shared/tools/policy.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/tools/test_policy.py` and `uv run mypy tests/m5_shared/tools/test_policy.py` are clean.


from pathlib import Path
from types import SimpleNamespace

from asf.m5_shared.tools.policy import PolicyEngine, PolicyVerdict, Verdict


def test_verdict_meets_contract() -> None:
    """Prove Verdict behaves as declared in src/asf/m5_shared/tools/policy.py."""
    assert Verdict.ALLOW.value == "allow"
    assert Verdict.DENY.value == "deny"
    assert Verdict.NEEDS_APPROVAL.value == "needs_approval"


def test_policy_verdict_meets_contract() -> None:
    """Prove PolicyVerdict behaves as declared in src/asf/m5_shared/tools/policy.py."""
    pv = PolicyVerdict(verdict=Verdict.ALLOW, reason="Approved")
    assert pv.verdict == Verdict.ALLOW
    assert pv.reason == "Approved"

    dumped = pv.model_dump()
    loaded = PolicyVerdict.model_validate(dumped)
    assert loaded == pv


def test_policy_engine_meets_contract(tmp_path: Path) -> None:
    """Prove PolicyEngine behaves as declared in src/asf/m5_shared/tools/policy.py."""
    engine = PolicyEngine()
    ws_dir = str(tmp_path)

    # Valid read tool
    read_spec = SimpleNamespace(
        name="read_file",
        roles=["worker", "developer"],
        destructive=False,
        needs_network=False,
        source="builtin",
    )
    inv_valid = SimpleNamespace(
        tool="read_file",
        args={"path": "main.py"},
        role="worker",
        workspace_dir=ws_dir,
    )
    res = engine.check(inv_valid, read_spec, "A", [])  # type: ignore[arg-type]
    assert res.verdict == Verdict.ALLOW

    # 1. Role mismatch
    inv_wrong_role = SimpleNamespace(
        tool="read_file",
        args={"path": "main.py"},
        role="reviewer",
        workspace_dir=ws_dir,
    )
    res_role = engine.check(inv_wrong_role, read_spec, "A", [])  # type: ignore[arg-type]
    assert res_role.verdict == Verdict.DENY
    assert "role" in res_role.reason.lower()

    # 2. Path escape
    inv_escape = SimpleNamespace(
        tool="read_file",
        args={"path": "../../secret.txt"},
        role="worker",
        workspace_dir=ws_dir,
    )
    res_escape = engine.check(inv_escape, read_spec, "A", [])  # type: ignore[arg-type]
    assert res_escape.verdict == Verdict.DENY
    assert "escape" in res_escape.reason.lower() or "denied" in res_escape.reason.lower()

    # 3. Path outside allowed_files
    inv_not_allowed = SimpleNamespace(
        tool="read_file",
        args={"path": "other.py"},
        role="worker",
        workspace_dir=ws_dir,
    )
    res_not_allowed = engine.check(inv_not_allowed, read_spec, "A", ["main.py"])  # type: ignore[arg-type]
    assert res_not_allowed.verdict == Verdict.DENY
    assert "allowed_files" in res_not_allowed.reason.lower()

    # 4. Destructive tool needs approval
    write_spec = SimpleNamespace(
        name="write_file",
        roles=["worker"],
        destructive=True,
        needs_network=False,
        source="builtin",
    )
    inv_write = SimpleNamespace(
        tool="write_file",
        args={"path": "main.py"},
        role="worker",
        workspace_dir=ws_dir,
    )
    res_write = engine.check(inv_write, write_spec, "A", [])  # type: ignore[arg-type]
    assert res_write.verdict == Verdict.NEEDS_APPROVAL

    # 5. Tier B network denied
    net_spec = SimpleNamespace(
        name="fetch",
        roles=["worker"],
        destructive=False,
        needs_network=True,
        source="builtin",
    )
    inv_net = SimpleNamespace(
        tool="fetch",
        args={},
        role="worker",
        workspace_dir=ws_dir,
    )
    res_net = engine.check(inv_net, net_spec, "B", [])  # type: ignore[arg-type]
    assert res_net.verdict == Verdict.DENY
    assert "network" in res_net.reason.lower()

    # 6. Tier B codeexec denied
    code_spec = SimpleNamespace(
        name="run_code",
        roles=["worker"],
        destructive=False,
        needs_network=False,
        source="codeexec",
    )
    res_code = engine.check(inv_net, code_spec, "B", [])  # type: ignore[arg-type]
    assert res_code.verdict == Verdict.DENY
    assert "code" in res_code.reason.lower()
