# FILE: src/asf/m5_shared/workspace/blobs.py
# ROLE: Content-addressed blob storage (sha-256) for documents, logs, diffs and manifests.
# ARCH REF: M5; p09 blobs
# OWNS: Blob files under the project data dir
# DOES NOT OWN: Deciding retention of tagged checkpoints
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/paths.py: AppPaths, get_paths (cross-platform base directories)
#   - called by src/asf/m5_shared/events/event_log.py: BlobStore
#   - called by src/asf/m5_shared/workspace/workspace.py: BlobStore
#   - called by src/asf/m2_request/document_ingestion.py: BlobStore
#   - called by src/asf/m3_orchestration/acceptance.py: BlobStore
#   - called by src/asf/cli/commands/report.py: BlobStore
#   - called by src/asf/cli/project_input.py: BlobStore
#   - called by src/asf/web/projection.py: BlobStore
#   - called by tests/m5_shared/workspace/test_blobs.py: BlobStore
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
from pathlib import Path

from asf.config.paths import AppPaths, get_paths


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
        """Store bytes; return 'sha256:<hex>' ref (idempotent)."""
        digest = hashlib.sha256(data).hexdigest()
        ref = f"sha256:{digest}"
        target: Path = self.root / digest[:2] / digest[2:]
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp_target: Path = target.with_suffix(".tmp")
            tmp_target.write_bytes(data)
            tmp_target.replace(target)
        return ref

    def get(self, ref: str) -> bytes:
        if ref.startswith("sha256:"):
            digest = ref[7:]
        else:
            digest = ref
        target: Path = self.root / digest[:2] / digest[2:]
        if not target.is_file():
            flat: Path = self.root / digest
            if flat.is_file():
                content: bytes = flat.read_bytes()
                return content
            raise FileNotFoundError(f"Blob ref not found: {ref}")
        content_target: bytes = target.read_bytes()
        return content_target
