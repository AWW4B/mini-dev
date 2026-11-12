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

import logging
import re
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from asf.contracts.requests import StructuredRequest
from asf.m5_shared.tools.builtin_tools import run_tests
from asf.m5_shared.workspace.blobs import BlobStore

logger = logging.getLogger(__name__)

_MAX_SCANNED_BYTES = 1_000_000
_FAILED_TEST = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.MULTILINE)
_SKIP_DIRS = frozenset({".git", ".venv", "node_modules", "__pycache__", ".factory"})

Regression = Callable[[Path, list[str]], tuple[int, str]]


class AcceptanceResult(BaseModel):
    passed: bool
    untraced: list[str]
    failing_tests: list[str]
    report_ref: str


def _test_texts(project_root: Path) -> list[str]:
    """The text of every test file (bounded), read once."""
    texts: list[str] = []
    for path in sorted(project_root.rglob("*.py")):
        if _SKIP_DIRS & set(path.relative_to(project_root).parts):
            continue
        if not (path.name.startswith("test_") or "tests" in path.relative_to(project_root).parts):
            continue
        try:
            if path.stat().st_size <= _MAX_SCANNED_BYTES:
                texts.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            logger.warning("could not read %s while tracing requirements", path, exc_info=True)
    return texts


def final_acceptance(
    request: StructuredRequest,
    project_root: Path,
    *,
    regression: Regression | None = None,
    blobs: BlobStore | None = None,
) -> AcceptanceResult:
    """Traceability matrix green (every requirement appears in a test) and the full regression green."""
    texts = _test_texts(project_root)
    traced = {req.req_id for req in request.requirements if any(req.req_id in text for text in texts)}
    untraced = [req.req_id for req in request.requirements if req.req_id not in traced]

    run = regression if regression is not None else run_tests
    exit_code, output = run(project_root, [])
    failing = list(dict.fromkeys(_FAILED_TEST.findall(output)))

    matrix = "\n".join(f"{req.req_id}\t{'traced' if req.req_id in traced else 'UNTRACED'}\t{req.text}" for req in request.requirements)
    report = f"Traceability matrix\n{matrix or '(no requirements)'}\n\nRegression exit code: {exit_code}\n{output}"
    report_ref = (blobs if blobs is not None else BlobStore()).put(report.encode("utf-8"))

    return AcceptanceResult(passed=not untraced and exit_code == 0, untraced=untraced, failing_tests=failing, report_ref=report_ref)
