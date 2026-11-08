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

import concurrent.futures
import io
import json
from typing import Any, BinaryIO

TOOL_REQUEST_KIND: str = "tool_request"
TOOL_RESPONSE_KIND: str = "tool_response"


class FramedChannel:
    reader: BinaryIO
    writer: BinaryIO
    tag: str

    def __init__(self, reader: BinaryIO, writer: BinaryIO, tag: str) -> None:
        self.reader = reader
        self.writer = writer
        self.tag = tag

    def send(self, kind: str, msg_id: str, body: dict[str, Any]) -> None:
        msg: dict[str, Any] = dict(body)
        msg["tag"] = self.tag
        msg["id"] = msg_id
        msg["kind"] = kind
        msg["body"] = body

        encoded = json.dumps(msg).encode("utf-8")
        header = len(encoded).to_bytes(4, byteorder="big")
        self.writer.write(header + encoded)
        self.writer.flush()

    def _read_exact(self, count: int) -> bytes:
        buf = bytearray()
        while len(buf) < count:
            chunk = self.reader.read(count - len(buf))
            if not chunk:
                break
            buf.extend(chunk)
        return bytes(buf)

    def _read_frame(self) -> dict[str, Any] | None:
        header = self._read_exact(4)
        if len(header) < 4:
            return None
        length = int.from_bytes(header, byteorder="big")
        payload = self._read_exact(length)
        if len(payload) < length:
            return None
        try:
            parsed = json.loads(payload.decode("utf-8"))
            if not isinstance(parsed, dict):
                return None
            if parsed.get("tag") != self.tag:
                return None
            return parsed
        except Exception:  # noqa: BLE001
            return None

    def receive(self, timeout_s: float) -> dict[str, Any] | None:
        if isinstance(self.reader, io.BytesIO):
            return self._read_frame()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._read_frame)
            try:
                return future.result(timeout=max(timeout_s, 0.001))
            except (TimeoutError, concurrent.futures.TimeoutError):
                return None
