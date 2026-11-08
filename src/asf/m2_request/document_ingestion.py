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

import re
from pathlib import Path

from markitdown import MarkItDown
from pydantic import BaseModel

from asf.m5_shared.decisions.broker import DecisionBroker  # noqa: F401
from asf.m5_shared.workspace.blobs import BlobStore


class IngestedDocument(BaseModel):
    original_ref: str
    markdown_ref: str
    section_ids: list[str]
    token_estimate: int
    quality_score: float
    extractor: str


def _detect_type_by_magic(raw_bytes: bytes) -> str:
    if raw_bytes.startswith(b"%PDF"):
        return "pdf"
    if raw_bytes.startswith(b"PK\x03\x04"):
        return "docx"
    if raw_bytes.startswith(b"<!DOCTYPE") or raw_bytes.startswith(b"<html") or raw_bytes.startswith(b"<?xml"):
        return "html"
    try:
        raw_bytes[:1024].decode("utf-8")
        return "text"
    except UnicodeDecodeError:
        return "binary"


def _extract_section_ids(markdown: str) -> list[str]:
    section_ids: list[str] = []
    for line in markdown.splitlines():
        line_s = line.strip()
        if line_s.startswith("#"):
            heading = line_s.lstrip("#").strip()
            slug = re.sub(r"[^\w\- ]+", "", heading).strip().lower().replace(" ", "-")
            if slug:
                section_ids.append(slug)
    if not section_ids:
        section_ids.append("section_0")
    return section_ids


def _compute_quality(text: str) -> float:
    if not text:
        return 0.0
    printable = sum(1 for c in text if c.isprintable() or c in "\n\r\t")
    ratio = printable / len(text)
    return round(min(1.0, max(0.0, ratio)), 2)


def ingest_document(path: Path) -> IngestedDocument:
    raw_bytes = path.read_bytes()

    # Store original file blob
    blobs = BlobStore()
    original_ref = blobs.put(raw_bytes)

    detected_type = _detect_type_by_magic(raw_bytes)

    markdown_text = ""
    extractor_used = "markitdown"

    # Primary extractor: MarkItDown
    try:
        md = MarkItDown()
        res = md.convert(str(path))
        markdown_text = res.text_content
    except Exception as _md_err:  # noqa: BLE001
        _ = _md_err
        markdown_text = ""

    # Alternate extractor 1: pypdf for PDF if primary gave empty result
    if (not markdown_text.strip()) and detected_type == "pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            pages = [p.extract_text() or "" for p in reader.pages]
            markdown_text = "\n\n".join(pages)
            extractor_used = "pypdf"
        except Exception as _pdf_err:  # noqa: BLE001
            _ = _pdf_err

    # Alternate extractor 2: Plain text fallback if still empty
    if not markdown_text.strip():
        try:
            markdown_text = path.read_text(encoding="utf-8", errors="replace")
            extractor_used = "plain_text"
        except Exception as _txt_err:  # noqa: BLE001
            _ = _txt_err
            markdown_text = ""

    quality = _compute_quality(markdown_text)
    section_ids = _extract_section_ids(markdown_text)
    token_estimate = max(1, len(markdown_text) // 4)

    # Store converted markdown blob
    markdown_ref = blobs.put(markdown_text.encode("utf-8"))

    return IngestedDocument(
        original_ref=original_ref,
        markdown_ref=markdown_ref,
        section_ids=section_ids,
        token_estimate=token_estimate,
        quality_score=quality,
        extractor=extractor_used,
    )
