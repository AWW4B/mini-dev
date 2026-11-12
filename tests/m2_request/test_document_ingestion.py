# FILE: tests/m2_request/test_document_ingestion.py
# ROLE: Tests that prove src/asf/m2_request/document_ingestion.py meets its DONE WHEN conditions.
# ARCH REF: M2; p03 Document Ingestion; D-28 (MarkItDown + pypdf; Docling optional extra); D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m2_request/document_ingestion.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m2_request/document_ingestion.py: DocumentNotIngestible, IngestedDocument, ingest_document (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m2_request/test_document_ingestion.py` on Windows and Linux once src/asf/m2_request/document_ingestion.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m2_request/test_document_ingestion.py` and `uv run mypy tests/m2_request/test_document_ingestion.py` are clean.

import zipfile
from pathlib import Path
from typing import Any

import pytest

import asf.m2_request.document_ingestion as ingest_mod
from asf.m2_request.document_ingestion import DocumentNotIngestible, IngestedDocument, ingest_document


def test_ingested_document_meets_contract() -> None:
    """Prove IngestedDocument behaves as declared in src/asf/m2_request/document_ingestion.py."""
    doc = IngestedDocument(
        original_ref="sha256:111",
        markdown_ref="sha256:222",
        section_ids=["intro", "details"],
        token_estimate=150,
        quality_score=0.95,
        extractor="markitdown",
    )
    assert doc.original_ref == "sha256:111"
    assert doc.markdown_ref == "sha256:222"
    assert doc.section_ids == ["intro", "details"]
    assert doc.token_estimate == 150
    assert doc.quality_score == 0.95
    assert doc.extractor == "markitdown"


def test_ingest_document_meets_contract(tmp_path: Path, fake_paths: Any) -> None:
    """Prove ingest_document behaves as declared in src/asf/m2_request/document_ingestion.py."""
    _ = fake_paths

    doc_file = tmp_path / "architecture.md"
    doc_file.write_text(
        "# System Architecture\n\n"
        "This describes the AI Software Factory architecture.\n\n"
        "## Components\n\n"
        "- M1 CLI\n"
        "- M2 Request\n"
        "- M3 Orchestration\n",
        encoding="utf-8",
    )

    ingested = ingest_document(doc_file)

    assert ingested.original_ref.startswith("sha256:")
    assert ingested.markdown_ref.startswith("sha256:")
    assert any("system-architecture" in sid or "components" in sid for sid in ingested.section_ids)
    assert ingested.token_estimate > 0
    assert ingested.quality_score >= 0.9
    assert ingested.extractor in {"markitdown", "plain_text", "docling", "pypdf"}


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_missing_file_asks_the_requester(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    with pytest.raises(DocumentNotIngestible) as info:
        ingest_document(tmp_path / "nope.pdf")
    assert "not readable" in info.value.reason


def test_empty_file_asks_the_requester(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    with pytest.raises(DocumentNotIngestible) as info:
        ingest_document(_write(tmp_path, "empty.txt", b""))
    assert "empty" in info.value.reason


def test_oversized_file_is_rejected_before_it_is_read(tmp_path: Path, fake_paths: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _ = fake_paths
    monkeypatch.setattr(ingest_mod, "MAX_DOCUMENT_BYTES", 10)
    with pytest.raises(DocumentNotIngestible) as info:
        ingest_document(_write(tmp_path, "big.txt", b"x" * 11))
    assert "limit" in info.value.reason


def test_unsupported_binary_asks_the_requester(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    with pytest.raises(DocumentNotIngestible) as info:
        ingest_document(_write(tmp_path, "blob.bin", bytes(range(256)) * 4))
    assert "unsupported" in info.value.reason


def test_failure_is_an_approval_required_error_with_a_clarify_request(tmp_path: Path) -> None:
    err = DocumentNotIngestible(tmp_path / "a.pdf", "it is encrypted")
    assert any(base.__name__ == "ApprovalRequired" for base in type(err).__mro__)
    req = err.decision_request(run_id="run-1", decision_id="dec-1")
    assert req.kind.value == "clarify"
    assert req.run_id == "run-1" and req.decision_id == "dec-1"
    assert "a.pdf" in req.question and "encrypted" in req.question
    assert req.default_on_timeout is None
    assert "skip_document" in req.options


def test_multibyte_character_cut_at_the_probe_boundary_is_still_text(tmp_path: Path) -> None:
    data = ("é" * 600).encode("utf-8")
    assert ingest_mod._detect_type_by_magic(tmp_path / "x.txt", data[:1023]) == "text"


def test_detection_ignores_the_extension(tmp_path: Path) -> None:
    pdf = _write(tmp_path, "report.txt", b"%PDF-1.7\n")
    assert ingest_mod._detect_type_by_magic(pdf, b"%PDF-1.7\n") == "pdf"
    assert ingest_mod._detect_type_by_magic(tmp_path / "p.pdf", b"<!DOCTYPE html><p>x</p>") == "html"


@pytest.mark.parametrize(
    ("member", "expected"),
    [("word/document.xml", "docx"), ("ppt/slides/slide1.xml", "pptx"), ("xl/workbook.xml", "xlsx"), ("data.csv", "binary")],
)
def test_zip_containers_are_told_apart_by_their_members(tmp_path: Path, member: str, expected: str) -> None:
    archive = tmp_path / "container.bin"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(member, "<x/>")
    assert ingest_mod._detect_type_by_magic(archive, archive.read_bytes()[:1024]) == expected


def test_quality_is_zero_without_text_and_drops_for_garbled_text() -> None:
    assert ingest_mod._compute_quality("") == 0.0
    assert ingest_mod._compute_quality("   \n\t ") == 0.0
    assert ingest_mod._compute_quality("clean text") == 1.0
    assert ingest_mod._compute_quality("ab\ufffd\ufffd\ufffd\ufffd") < 0.5


def test_markitdown_is_created_once() -> None:
    assert ingest_mod._get_markitdown() is ingest_mod._get_markitdown()


def test_alternate_extractor_runs_when_the_primary_fails(tmp_path: Path, fake_paths: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _ = fake_paths

    def broken(_path: Path) -> str:
        raise ValueError("converter crashed")

    monkeypatch.setattr(ingest_mod, "_extract_markitdown", broken)
    doc = ingest_document(_write(tmp_path, "notes.md", b"# Title\n\nSome readable requirements text.\n"))
    assert doc.extractor == "plain_text"
    assert "title" in doc.section_ids


def test_at_most_two_alternates_are_configured_per_type() -> None:
    assert len(ingest_mod._alternates("pdf")) <= 2
    assert [name for name, _ in ingest_mod._alternates("pdf")][-1] == "pypdf"
    assert ingest_mod._alternates("binary") == []
