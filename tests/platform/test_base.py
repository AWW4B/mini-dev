# FILE: tests/platform/test_base.py
# ROLE: Tests that prove src/asf/platform/base.py meets its DONE WHEN conditions.
# ARCH REF: FR-4 (one platform-adapter interface); D-15; D-20; D-21; IF-14 sandbox tier; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/platform/base.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/platform/base.py: SandboxSpec, ProcessResult, SandboxBackend, PlatformAdapter (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/platform/test_base.py` on Windows and Linux once src/asf/platform/base.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/platform/test_base.py` and `uv run mypy tests/platform/test_base.py` are clean.


from pathlib import Path
from typing import Any

from asf.platform.base import PlatformAdapter, ProcessResult, SandboxBackend, SandboxSpec  # noqa: F401


def test_sandbox_spec_meets_contract(tmp_path: Path) -> None:
    """Prove SandboxSpec behaves as declared in src/asf/platform/base.py."""
    spec = SandboxSpec(
        argv=["python", "-c", "print(1)"],
        cwd=tmp_path,
        writable_paths=[tmp_path / "out"],
        readable_paths=[tmp_path / "in"],
        network=False,
        timeout_s=60,
        env={"FOO": "BAR"},
        extra_fds=[],
    )
    assert spec.argv == ["python", "-c", "print(1)"]
    assert spec.cwd == tmp_path
    assert spec.network is False
    assert spec.timeout_s == 60
    assert spec.env == {"FOO": "BAR"}

    # Default values check
    default_spec = SandboxSpec(
        argv=["echo", "hi"],
        cwd=tmp_path,
        writable_paths=[],
        readable_paths=[],
    )
    assert default_spec.network is False
    assert default_spec.timeout_s == 120
    assert default_spec.env == {}
    assert default_spec.extra_fds == []


def test_process_result_meets_contract() -> None:
    """Prove ProcessResult behaves as declared in src/asf/platform/base.py."""
    res = ProcessResult(
        exit_code=0,
        stdout=b"output",
        stderr=b"",
        timed_out=False,
        duration_ms=42,
    )
    assert res.exit_code == 0
    assert res.stdout == b"output"
    assert res.stderr == b""
    assert res.timed_out is False
    assert res.duration_ms == 42


def test_sandbox_backend_meets_contract() -> None:
    """Prove SandboxBackend protocol can be satisfied by a class."""

    class DummySandboxBackend:
        name = "dummy"
        tier: Any = "A"

        def available(self) -> bool:
            return True

        def run(self, spec: SandboxSpec) -> ProcessResult:
            return ProcessResult(
                exit_code=0,
                stdout=b"",
                stderr=b"",
                timed_out=False,
                duration_ms=10,
            )

    backend: SandboxBackend = DummySandboxBackend()
    assert backend.name == "dummy"
    assert backend.available() is True


def test_platform_adapter_meets_contract(tmp_path: Path) -> None:
    """Prove PlatformAdapter protocol can be satisfied by a class."""

    class DummyAdapter:
        name = "dummy"

        def sandbox(self) -> SandboxBackend:
            raise NotImplementedError

        def run_process(self, argv: list[str], cwd: Path, timeout_s: int, env: dict[str, str] | None = None) -> ProcessResult:
            return ProcessResult(
                exit_code=0,
                stdout=b"",
                stderr=b"",
                timed_out=False,
                duration_ms=5,
            )

        def kill_tree(self, pid: int) -> None:
            pass

        def lock_file(self, path: Path, timeout_s: float) -> object:
            return None

        def resolve_within(self, root: Path, candidate: str) -> Path:
            return root / candidate

        def install_interrupt_handler(self, on_interrupt: object) -> None:
            pass

        def detach(self, argv: list[str], log_path: Path) -> int:
            return 1234

    adapter: PlatformAdapter = DummyAdapter()
    assert adapter.name == "dummy"
    assert adapter.resolve_within(tmp_path, "sub") == tmp_path / "sub"
