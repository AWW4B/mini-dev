# FILE: src/asf/m2_request/document_ingestion.py
# ROLE: Converts attached documents to Markdown with a quality check and alternate extractors, storing original, .md and section index.
# ARCH REF: M2; p03 Document Ingestion; D-28 (MarkItDown + pypdf; Docling optional extra)
# OWNS: Type detection, extraction, quality scoring
# DOES NOT OWN: Understanding the content (request_understanding)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (content-addressed blobs)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (IF-03 decisions)
#   - called by src/asf/m2_request/pipeline.py: ingest_document
#   - called by tests/m2_request/test_document_ingestion.py: IngestedDocument, ingest_document
#   - emits/consumes: raises DecisionRequest (kind CLARIFY) for unsupported, oversized or unreadable files
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Detect type by magic bytes, not extension.
#   9. Use Docling only if importable (the [docs-advanced] extra); never require it.
#   10. At most 2 alternate extractors.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m2_request/test_document_ingestion.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m2_request/document_ingestion.py` and `uv run mypy src/asf/m2_request/document_ingestion.py` are clean.

from pathlib import Path

from pydantic import BaseModel


class IngestedDocument(BaseModel):
    original_ref: str
    markdown_ref: str
    section_ids: list[str]
    token_estimate: int
    quality_score: float
    extractor: str


def ingest_document(path: Path) -> IngestedDocument:
    raise NotImplementedError
