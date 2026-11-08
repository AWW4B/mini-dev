# FILE: src/asf/m2_request/intake_router.py
# ROLE: Receives IF-01, creates the request record idempotently, tags provenance and fans out to document and repository intake.
# ARCH REF: M2; p03 Intake Router; IF-01 SubmitRequest; IF-02
# OWNS: Request records, fan-out and barrier
# DOES NOT OWN: Extraction (document_ingestion, repository_intake)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/requests.py: SubmitRequest, StructuredRequest (IF-01/IF-02)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (IF-16 state)
#   - imports from src/asf/m2_request/pipeline.py: build_request_graph (the M2 graph)
#   - called by src/asf/cli/commands/run.py: submit
#   - called by tests/m2_request/test_intake_router.py: submit
#   - emits/consumes: emits STATE_CHANGED for the request record
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Idempotency key = hash(project_id, text, attachment hashes); a duplicate returns the existing request id.
#   6. Mark every text source with provenance (user, document, repo); document and repo text is untrusted.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m2_request/test_intake_router.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m2_request/intake_router.py` and `uv run mypy src/asf/m2_request/intake_router.py` are clean.

from asf.contracts.requests import StructuredRequest, SubmitRequest


def submit(request: SubmitRequest) -> StructuredRequest:
    """IF-01 in, IF-02 out (runs the M2 graph to completion or to a HITL interrupt)."""
    raise NotImplementedError
