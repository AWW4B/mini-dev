# FILE: tests/m5_shared/tools/codeexec/test_channel.py
# ROLE: Tests that prove src/asf/m5_shared/tools/codeexec/channel.py meets its DONE WHEN conditions.
# ARCH REF: M5; p12; D-19a (framing so print() cannot spoof tool requests); D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/tools/codeexec/channel.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/tools/codeexec/channel.py: FramedChannel, TOOL_REQUEST_KIND, TOOL_RESPONSE_KIND (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/tools/codeexec/test_channel.py` on Windows and Linux once src/asf/m5_shared/tools/codeexec/channel.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/tools/codeexec/test_channel.py` and `uv run mypy tests/m5_shared/tools/codeexec/test_channel.py` are clean.

import io

from asf.m5_shared.tools.codeexec.channel import (
    TOOL_REQUEST_KIND,
    TOOL_RESPONSE_KIND,
    FramedChannel,
)


def test_framed_channel_meets_contract() -> None:
    """Prove FramedChannel behaves as declared in src/asf/m5_shared/tools/codeexec/channel.py."""
    buf = io.BytesIO()
    channel = FramedChannel(reader=buf, writer=buf, tag="secret-tag-123")

    # Send a request
    channel.send(
        TOOL_REQUEST_KIND,
        "req-001",
        {"tool": "read_file", "path": "test.txt"},
    )

    # Rewind to read
    buf.seek(0)
    received = channel.receive(timeout_s=1.0)
    assert received is not None
    assert received["tag"] == "secret-tag-123"
    assert received["id"] == "req-001"
    assert received["kind"] == TOOL_REQUEST_KIND
    assert received["tool"] == "read_file"
    assert received["body"] == {"tool": "read_file", "path": "test.txt"}

    # Wrong tag must be rejected
    buf.seek(0)
    bad_channel = FramedChannel(reader=buf, writer=buf, tag="wrong-tag")
    assert bad_channel.receive(timeout_s=1.0) is None

    # Empty buffer returns None
    empty_buf = io.BytesIO()
    empty_channel = FramedChannel(reader=empty_buf, writer=empty_buf, tag="any-tag")
    assert empty_channel.receive(timeout_s=0.1) is None


def test_t_o_o_l__r_e_q_u_e_s_t__k_i_n_d_meets_contract() -> None:
    """Prove TOOL_REQUEST_KIND behaves as declared in src/asf/m5_shared/tools/codeexec/channel.py."""
    assert TOOL_REQUEST_KIND == "tool_request"


def test_t_o_o_l__r_e_s_p_o_n_s_e__k_i_n_d_meets_contract() -> None:
    """Prove TOOL_RESPONSE_KIND behaves as declared in src/asf/m5_shared/tools/codeexec/channel.py."""
    assert TOOL_RESPONSE_KIND == "tool_response"
