# FILE: tests/m2_request/test_document_ingestion.py
# ROLE: Tests that prove src/asf/m2_request/document_ingestion.py meets its DONE WHEN conditions.
# ARCH REF: M2; p03 Document Ingestion; D-28 (MarkItDown + pypdf; Docling optional extra); D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m2_request/document_ingestion.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m2_request/document_ingestion.py: IngestedDocument, ingest_document (unit under test)
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

from pathlib import Path
from typing import Any

from asf.m2_request.document_ingestion import IngestedDocument, ingest_document


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
