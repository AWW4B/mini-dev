# FILE: src/asf/m3_orchestration/acceptance.py
# ROLE: Final acceptance: traceability matrix green and full regression green before DONE.
# ARCH REF: M3; p04 final acceptance
# OWNS: Final gate and report assembly
# DOES NOT OWN: Per-leaf gates (M4 verification)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/requests.py: StructuredRequest (requirements)
#   - imports from src/asf/m5_shared/tools/builtin_tools.py: run_tests (regression)
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (content-addressed blobs)
#   - called by src/asf/m3_orchestration/run_graph.py: final_acceptance
#   - called by tests/m3_orchestration/test_acceptance.py: AcceptanceResult, final_acceptance
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/test_acceptance.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/acceptance.py` and `uv run mypy src/asf/m3_orchestration/acceptance.py` are clean.

from pathlib import Path

from pydantic import BaseModel

from asf.contracts.requests import StructuredRequest


class AcceptanceResult(BaseModel):
    passed: bool
    untraced: list[str]
    failing_tests: list[str]
    report_ref: str


def final_acceptance(request: StructuredRequest, project_root: Path) -> AcceptanceResult:
    raise NotImplementedError
