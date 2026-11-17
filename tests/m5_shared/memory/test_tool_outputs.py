# FILE: tests/m5_shared/memory/test_tool_outputs.py
# ROLE: Tests for src/asf/m5_shared/memory/tool_outputs.py.
# ARCH REF: M5; p12 Context & Memory Service; docs/architecture/MEMORY_ARCHITECTURE.md
# OWNS: Tests of tool_outputs
# DOES NOT OWN: Production code
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/memory/tool_outputs.py: ToolOutputPolicy (unit under test)
#   - imports from src/asf/m5_shared/memory/device_budget.py: load_memory_config (packaged config)
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (offloaded output)
#   - imports from tests/conftest.py: fake_paths (isolated app directories)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/memory/test_tool_outputs.py` on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/memory/test_tool_outputs.py` and `uv run mypy tests/m5_shared/memory/test_tool_outputs.py` are clean.

from pathlib import Path
from typing import Any

import pytest

from asf.m5_shared.memory.device_budget import load_memory_config
from asf.m5_shared.memory.tool_outputs import ToolOutputPolicy
from asf.m5_shared.workspace.blobs import BlobStore


@pytest.fixture
def config(fake_paths: Any) -> dict[str, Any]:
    _ = fake_paths
    return load_memory_config()


def test_small_results_pass_unchanged(config: dict[str, Any]) -> None:
    out = ToolOutputPolicy(config, 8192).shape("read_file", "x = 1\n")
    assert out.text == "x = 1\n" and not out.truncated


def test_large_results_are_cut_to_their_share_keeping_head_and_tail(config: dict[str, Any]) -> None:
    policy = ToolOutputPolicy(config, 8192)
    log = "START\n" + "noise\n" * 5000 + "FAILED test_x: AssertionError\n"
    out = policy.shape("run_tests", log, status="error")
    assert out.truncated and "START" in out.text and "FAILED test_x" in out.text and "chars omitted" in out.text
    assert out.kept_chars <= policy.cap_chars("builtin") + 200


def test_errors_keep_more_tail_and_file_reads_more_head(config: dict[str, Any]) -> None:
    policy = ToolOutputPolicy(config, 8192)
    text = "".join(f"line {i}\n" for i in range(5000))
    read = policy.shape("read_file", text)
    failed = policy.shape("run_tests", text, status="error")
    def head(text: str) -> int:
        return len(text.split("... [")[0])

    assert head(read.text) > head(failed.text)


def test_very_large_results_are_offloaded_whole(config: dict[str, Any], tmp_path: Path) -> None:
    blobs = BlobStore(tmp_path / "blobs")
    out = ToolOutputPolicy(config, 8192, blobs=blobs).shape("run_tests", "y" * 200_000, status="error")
    assert out.offloaded_ref and f"blob:{out.offloaded_ref}" in out.text
    assert len(blobs.get(out.offloaded_ref)) == 200_000


def test_mcp_output_is_marked_untrusted_and_gets_a_smaller_share(config: dict[str, Any]) -> None:
    policy = ToolOutputPolicy(config, 8192)
    out = policy.shape("search", "z" * 50_000, source="mcp", origin="web-search")
    assert out.untrusted and out.text.startswith("[untrusted output from MCP server web-search")
    assert policy.cap_chars("mcp") < policy.cap_chars("builtin")


def test_only_the_latest_results_stay_in_full(config: dict[str, Any]) -> None:
    policy = ToolOutputPolicy(config, 8192)
    results = [policy.shape("read_file", f"content {i}") for i in range(5)]
    texts = policy.clear_stale(results)
    assert texts[-policy.keep_recent :] == [f"content {i}" for i in range(5 - policy.keep_recent, 5)]
    assert all(t.startswith("[result cleared") for t in texts[: 5 - policy.keep_recent])


def test_compaction_starts_at_its_share_of_the_input_window(config: dict[str, Any]) -> None:
    policy = ToolOutputPolicy(config, 1000)
    assert not policy.should_compact(100) and policy.should_compact(4000)
