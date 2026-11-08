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


from asf.m5_shared.tools.codeexec.channel import TOOL_REQUEST_KIND, TOOL_RESPONSE_KIND, FramedChannel  # noqa: F401


def test_framed_channel_meets_contract() -> None:
    """Prove FramedChannel behaves as declared in src/asf/m5_shared/tools/codeexec/channel.py."""
    raise NotImplementedError("write this test before implementing FramedChannel")

def test_t_o_o_l__r_e_q_u_e_s_t__k_i_n_d_meets_contract() -> None:
    """Prove TOOL_REQUEST_KIND behaves as declared in src/asf/m5_shared/tools/codeexec/channel.py."""
    raise NotImplementedError("write this test before implementing TOOL_REQUEST_KIND")

def test_t_o_o_l__r_e_s_p_o_n_s_e__k_i_n_d_meets_contract() -> None:
    """Prove TOOL_RESPONSE_KIND behaves as declared in src/asf/m5_shared/tools/codeexec/channel.py."""
    raise NotImplementedError("write this test before implementing TOOL_RESPONSE_KIND")
