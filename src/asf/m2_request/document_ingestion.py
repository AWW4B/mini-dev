# FILE: src/asf/m2_request/document_ingestion.py
# ROLE: Converts attached documents to Markdown with a quality check and alternate extractors, storing original, .md and section index.
# ARCH REF: M2; p03 Document Ingestion; D-28 (MarkItDown + pypdf; Docling optional extra)
# OWNS: Type detection, extraction, quality scoring
# DOES NOT OWN: Understanding the content (request_understanding)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (content-addressed blobs)
#   - imports from src/asf/m5_shared/decisions/broker.py: DecisionBroker (IF-03 decisions)
#   - imports from src/asf/contracts/decisions.py: DecisionRequest (the CLARIFY request carried by DocumentNotIngestible)
#   - imports from src/asf/contracts/errors.py: ApprovalRequired (base class of DocumentNotIngestible)
#   - called by src/asf/m2_request/pipeline.py: ingest_document, DocumentNotIngestible
#   - called by tests/m2_request/test_document_ingestion.py: DocumentNotIngestible, IngestedDocument, ingest_document
#   - emits/consumes: raises DocumentNotIngestible (an ApprovalRequired carrying a DecisionRequest of kind CLARIFY via decision_request()) for unsupported, oversized or unreadable files; the caller hands it to the DecisionBroker
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

import codecs
import importlib
import importlib.util
import logging
import re
import zipfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from asf.contracts.decisions import DecisionRequest
from asf.contracts.errors import ApprovalRequired
from asf.m5_shared.decisions.broker import DecisionBroker  # noqa: F401
from asf.m5_shared.workspace.blobs import BlobStore

logger = logging.getLogger(__name__)

MAX_DOCUMENT_BYTES = 50 * 1024 * 1024
QUALITY_ACCEPT = 0.9
MAX_ALTERNATE_EXTRACTORS = 2
_MAGIC_PROBE_BYTES = 1024

_markitdown: Any = None


class IngestedDocument(BaseModel):
    original_ref: str
    markdown_ref: str
    section_ids: list[str]
    token_estimate: int
    quality_score: float
    extractor: str


class DocumentNotIngestible(ApprovalRequired):
    """The file is unsupported, oversized or unreadable; the requester must decide what to do (DecisionKind CLARIFY)."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"Cannot ingest '{path.name}': {reason}. Provide a different file or format, or skip this document.")
        self.path = path
        self.reason = reason

    def decision_request(self, run_id: str, decision_id: str, requester: str = "asf.m2_request.document_ingestion") -> DecisionRequest:
        """Build the IF-03 CLARIFY request for this failure; the caller hands it to the DecisionBroker."""
        return DecisionRequest.model_validate(
            {
                "decision_id": decision_id,
                "run_id": run_id,
                "kind": "clarify",
                "requester": requester,
                "question": f"The attached document '{self.path.name}' could not be read: {self.reason}. How should we proceed?",
                "options": ["skip_document", "abort"],
                "default_on_timeout": None,
                "evidence_refs": [],
            }
        )


def _detect_type_by_magic(path: Path, head: bytes) -> str:
    """Classify by content, never by extension (header rule 8)."""
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        return _classify_zip(path)
    stripped = head.lstrip()[:16].lower()
    if stripped.startswith((b"<!doctype", b"<html", b"<?xml")):
        return "html"
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        decoder.decode(head, final=False)  # tolerates a multi-byte character cut at the probe boundary
    except UnicodeDecodeError:
        return "binary"
    return "text"


def _classify_zip(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except (zipfile.BadZipFile, OSError):
        return "binary"
    if "word/document.xml" in names:
        return "docx"
    if any(n.startswith("ppt/") for n in names):
        return "pptx"
    if any(n.startswith("xl/") for n in names):
        return "xlsx"
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
    """Share of printable characters, minus the garbled-character (U+FFFD) rate; 0.0 when there is no text at all."""
    if not text.strip():
        return 0.0
    printable = sum(1 for c in text if c.isprintable() or c in "\n\r\t")
    garbled = text.count("�")
    ratio = (printable - garbled) / len(text)
    return round(min(1.0, max(0.0, ratio)), 2)


def _get_markitdown() -> Any:
    global _markitdown
    if _markitdown is None:
        from markitdown import MarkItDown  # the converter costs about a second to import and only document ingestion needs it

        _markitdown = MarkItDown()
    return _markitdown


def _extract_markitdown(path: Path) -> str:
    return str(_get_markitdown().convert(str(path)).text_content or "")


def _extract_docling(path: Path) -> str:
    converter_module = importlib.import_module("docling.document_converter")
    result: Any = converter_module.DocumentConverter().convert(str(path))
    return str(result.document.export_to_markdown())


def _extract_pypdf(path: Path) -> str:
    import pypdf

    reader = pypdf.PdfReader(str(path))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def _extract_plain_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _alternates(detected_type: str) -> list[tuple[str, Any]]:
    """Alternate extractors for this file type, best first (header rules 9 and 10)."""
    alternates: list[tuple[str, Any]] = []
    if detected_type == "pdf":
        if importlib.util.find_spec("docling") is not None:
            alternates.append(("docling", _extract_docling))
        alternates.append(("pypdf", _extract_pypdf))
    elif detected_type in {"text", "html"}:
        alternates.append(("plain_text", _extract_plain_text))
    return alternates[:MAX_ALTERNATE_EXTRACTORS]


def _try_extract(name: str, extractor: Any, path: Path) -> str:
    """Run one extractor; a failing extractor is logged and counts as empty so the next one can run."""
    try:
        return str(extractor(path))
    except Exception:  # noqa: BLE001 - third-party extractors raise arbitrary exception types
        logger.warning("extractor %s failed for %s", name, path.name, exc_info=True)
        return ""


def ingest_document(path: Path) -> IngestedDocument:
    try:
        size = path.stat().st_size
    except OSError as err:
        raise DocumentNotIngestible(path, f"the file is not readable ({err.strerror or err})") from err
    if size == 0:
        raise DocumentNotIngestible(path, "the file is empty")
    if size > MAX_DOCUMENT_BYTES:
        raise DocumentNotIngestible(path, f"the file is {size // (1024 * 1024)} MB, over the {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB limit")

    try:
        with path.open("rb") as handle:
            head = handle.read(_MAGIC_PROBE_BYTES)
        raw_bytes = path.read_bytes()
    except OSError as err:
        raise DocumentNotIngestible(path, f"the file is not readable ({err.strerror or err})") from err

    detected_type = _detect_type_by_magic(path, head)

    best_text = _try_extract("markitdown", _extract_markitdown, path)
    best_quality = _compute_quality(best_text)
    extractor_used = "markitdown"

    if best_quality < QUALITY_ACCEPT:
        for name, extractor in _alternates(detected_type):
            text = _try_extract(name, extractor, path)
            quality = _compute_quality(text)
            if quality > best_quality:
                best_text, best_quality, extractor_used = text, quality, name
            if best_quality >= QUALITY_ACCEPT:
                break

    if not best_text.strip():
        kind = "an unsupported file type" if detected_type == "binary" else "no extractable text (a scanned or image-only file?)"
        raise DocumentNotIngestible(path, f"it contains {kind}")

    blobs = BlobStore()
    original_ref = blobs.put(raw_bytes)
    markdown_ref = blobs.put(best_text.encode("utf-8"))

    return IngestedDocument(
        original_ref=original_ref,
        markdown_ref=markdown_ref,
        section_ids=_extract_section_ids(best_text),
        token_estimate=max(1, len(best_text) // 4),
        quality_score=best_quality,
        extractor=extractor_used,
    )
