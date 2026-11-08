# FILE: tests/m5_shared/tools/codeexec/test_facade_gen.py
# ROLE: Tests that prove src/asf/m5_shared/tools/codeexec/facade_gen.py meets its DONE WHEN conditions.
# ARCH REF: M5; p12; D-19a; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/tools/codeexec/facade_gen.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/tools/codeexec/facade_gen.py: generate_facade (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/tools/codeexec/test_facade_gen.py` on Windows and Linux once src/asf/m5_shared/tools/codeexec/facade_gen.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/tools/codeexec/test_facade_gen.py` and `uv run mypy tests/m5_shared/tools/codeexec/test_facade_gen.py` are clean.

from types import SimpleNamespace
from typing import Any

from asf.m5_shared.tools.codeexec.facade_gen import generate_facade


def test_generate_facade_meets_contract() -> None:
    """Prove generate_facade behaves as declared in src/asf/m5_shared/tools/codeexec/facade_gen.py."""
    specs: list[Any] = [
        SimpleNamespace(
            name="read_file",
            description="Read the contents of a file.",
            args_schema={
                "properties": {
                    "path": {"type": "string", "description": "Target path"},
                    "offset": {"type": "integer", "description": "Byte offset"},
                },
                "required": ["path"],
            },
            roles=["T3"],
            source="builtin",
        ),
        SimpleNamespace(
            name="search_code",
            description="Search for symbols.",
            args_schema={
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
            roles=["T3"],
            source="builtin",
        ),
    ]

    source = generate_facade(specs)
    assert isinstance(source, str)
    assert "def read_file" in source
    assert "def search_code" in source

    # Compile source
    code_obj = compile(source, "tools.py", "exec")
    assert code_obj is not None

    # Execute in a namespace
    ns: dict[str, Any] = {}
    exec(code_obj, ns)  # noqa: S102

    assert callable(ns.get("read_file"))
    assert callable(ns.get("search_code"))

    # Test invoking through mock dispatcher
    called_calls: list[tuple[str, dict[str, Any]]] = []

    def mock_dispatcher(name: str, args: dict[str, Any]) -> str:
        called_calls.append((name, args))
        return f"result_for_{name}"

    ns["_mock_dispatcher"] = mock_dispatcher
    res = ns["read_file"](path="src/main.py", offset=10)
    assert res == "result_for_read_file"
    assert len(called_calls) == 1
    assert called_calls[0] == ("read_file", {"path": "src/main.py", "offset": 10})
