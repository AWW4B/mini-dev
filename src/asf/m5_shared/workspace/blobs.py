# FILE: src/asf/m5_shared/workspace/blobs.py
# ROLE: Content-addressed blob storage (sha-256) for documents, logs, diffs and manifests.
# ARCH REF: M5; p09 blobs
# OWNS: Blob files under the project data dir
# DOES NOT OWN: Deciding retention of tagged checkpoints
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/paths.py: AppPaths, get_paths (cross-platform base directories)
#   - imports from src/asf/contracts/errors.py: AsfError (base of BlobNotFound)
#   - called by src/asf/m5_shared/events/event_log.py: BlobStore
#   - called by src/asf/m5_shared/workspace/workspace.py: BlobStore
#   - called by src/asf/m2_request/document_ingestion.py: BlobStore
#   - called by src/asf/m3_orchestration/acceptance.py: BlobStore
#   - called by src/asf/cli/commands/report.py: BlobStore
#   - called by src/asf/cli/project_input.py: BlobStore
#   - called by src/asf/web/projection.py: BlobStore
#   - called by tests/m5_shared/workspace/test_blobs.py: BlobNotFound, BlobStore
#   - called by tests/m3_orchestration/test_acceptance.py: BlobStore
#   - called by tests/m3_orchestration/test_run_graph.py: BlobStore
#   - called by src/asf/m3_orchestration/run_graph.py: BlobStore
#   - called by tests/cli/test_project_input.py: BlobStore
#   - called by tests/cli/commands/test_report.py: BlobStore
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/workspace/test_blobs.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/workspace/blobs.py` and `uv run mypy src/asf/m5_shared/workspace/blobs.py` are clean.

import hashlib
import os
import re
import tempfile
from pathlib import Path

from asf.config.paths import AppPaths, get_paths
from asf.contracts.errors import AsfError

_DIGEST = re.compile(r"[0-9a-f]{64}")


class BlobNotFound(AsfError, FileNotFoundError):
    """No blob exists for this reference (also a FileNotFoundError, so existing handlers keep working)."""


class BlobStore:
    root: Path

    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            paths: AppPaths = get_paths()
            self.root = paths.data_dir / "blobs"
        else:
            self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes) -> str:
        """Store bytes; return 'sha256:<hex>' ref (idempotent, safe against concurrent writers)."""
        digest = hashlib.sha256(data).hexdigest()
        ref = f"sha256:{digest}"
        target: Path = self.root / digest[:2] / digest[2:]
        if target.is_file():
            return ref
        target.parent.mkdir(parents=True, exist_ok=True)
        # A unique temp file in the same directory: two writers of the same blob never share a temp name,
        # and the final os.replace is atomic, so readers only ever see a complete blob.
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            try:
                os.replace(tmp_name, target)
            except PermissionError:
                # Windows refuses to replace a file another process has just created or is reading; the content
                # is identical by construction, so an existing target means the blob is stored.
                if not target.is_file():
                    raise
        finally:
            Path(tmp_name).unlink(missing_ok=True)
        return ref

    def get(self, ref: str) -> bytes:
        digest = ref[7:] if ref.startswith("sha256:") else ref
        if _DIGEST.fullmatch(digest) is None:
            raise BlobNotFound(f"'{ref}' is not a valid blob reference (expected 'sha256:' and 64 hex characters)")
        target: Path = self.root / digest[:2] / digest[2:]
        if target.is_file():
            content: bytes = target.read_bytes()
            return content
        flat: Path = self.root / digest
        if flat.is_file():
            flat_content: bytes = flat.read_bytes()
            return flat_content
        raise BlobNotFound(f"Blob ref not found: {ref}")
