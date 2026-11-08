# FILE: tests/m5_shared/tools/codeexec/test_search.py
# ROLE: Tests that prove src/asf/m5_shared/tools/codeexec/search.py meets its DONE WHEN conditions.
# ARCH REF: M5; p12; D-19; D-19a; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/tools/codeexec/search.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/tools/codeexec/search.py: search_tools (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/tools/codeexec/test_search.py` on Windows and Linux once src/asf/m5_shared/tools/codeexec/search.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/tools/codeexec/test_search.py` and `uv run mypy tests/m5_shared/tools/codeexec/test_search.py` are clean.

from types import SimpleNamespace
from typing import Any

from asf.m5_shared.tools.codeexec.search import search_tools


def test_search_tools_meets_contract() -> None:
    """Prove search_tools behaves as declared in src/asf/m5_shared/tools/codeexec/search.py."""
    spec_read = SimpleNamespace(
        name="read_file",
        description="Read file contents from disk.",
        args_schema={"properties": {"path": {"type": "string"}}},
        destructive=False,
        needs_network=False,
        roles=["T3", "T2"],
        source="builtin",
    )
    spec_delete = SimpleNamespace(
        name="delete_file",
        description="Permanently delete a file.",
        args_schema={"properties": {"path": {"type": "string"}}},
        destructive=True,
        needs_network=False,
        roles=["T3"],
        source="builtin",
    )
    spec_network = SimpleNamespace(
        name="fetch_url",
        description="Fetch content from web URL.",
        args_schema={"properties": {"url": {"type": "string"}}},
        destructive=False,
        needs_network=True,
        roles=["T3"],
        source="mcp:web",
    )

    class FakeRegistry:
        def specs_for(self, role: str) -> list[Any]:
            all_specs = [spec_read, spec_delete, spec_network]
            return [s for s in all_specs if role in s.roles]

    fake_reg = FakeRegistry()

    # 1. Query matching by name (detail="names")
    res_names = search_tools(fake_reg, role="T3", query="read", detail="names")  # type: ignore[arg-type]
    assert len(res_names) == 1
    assert res_names[0] == {"name": "read_file"}

    # 2. Query matching by description (detail="descriptions")
    res_desc = search_tools(fake_reg, role="T3", query="web", detail="descriptions")  # type: ignore[arg-type]
    assert len(res_desc) == 1
    assert res_desc[0]["name"] == "fetch_url"
    assert "Fetch content" in res_desc[0]["description"]

    # 3. Query all with full details (detail="full")
    res_full = search_tools(fake_reg, role="T3", query="*", detail="full")  # type: ignore[arg-type]
    assert len(res_full) == 3
    delete_entry = next(r for r in res_full if r["name"] == "delete_file")
    assert delete_entry["destructive"] is True
    assert delete_entry["source"] == "builtin"
    assert "args_schema" in delete_entry

    # 4. Filter by role (T2 cannot see delete_file or fetch_url)
    res_t2 = search_tools(fake_reg, role="T2", query="*", detail="names")  # type: ignore[arg-type]
    assert len(res_t2) == 1
    assert res_t2[0]["name"] == "read_file"
