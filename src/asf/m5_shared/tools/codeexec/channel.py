# FILE: src/asf/m5_shared/tools/codeexec/channel.py
# ROLE: Framed, tagged JSON messages on a dedicated pipe between a code_exec script and the parent, separate from the script stdout/stderr.
# ARCH REF: M5; p12; D-19a (framing so print() cannot spoof tool requests)
# OWNS: Wire format and framing
# DOES NOT OWN: Process creation (runner.py)
# CONNECTS TO (external boundaries only):
#   - called by src/asf/m5_shared/tools/codeexec/runner.py: FramedChannel
#   - called by tests/m5_shared/tools/codeexec/test_channel.py: FramedChannel, TOOL_REQUEST_KIND, TOOL_RESPONSE_KIND
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Frame = 4-byte big-endian length + UTF-8 JSON object with fields tag, id, kind; reject frames without the per-run random tag.
#   6. Use a dedicated pipe/fd pair passed to the child, never the child stdout/stderr.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/tools/codeexec/test_channel.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/tools/codeexec/channel.py` and `uv run mypy src/asf/m5_shared/tools/codeexec/channel.py` are clean.

from typing import Any, BinaryIO

TOOL_REQUEST_KIND: str = "tool_request"
TOOL_RESPONSE_KIND: str = "tool_response"


class FramedChannel:
    def __init__(self, reader: BinaryIO, writer: BinaryIO, tag: str) -> None:
        raise NotImplementedError

    def send(self, kind: str, msg_id: str, body: dict[str, Any]) -> None:
        raise NotImplementedError

    def receive(self, timeout_s: float) -> dict[str, Any] | None:
        raise NotImplementedError
