# FILE: src/asf/m4_execution/verification/reviewer.py
# ROLE: Optional reviewer model for risky changes: diff vs contract findings; advisory only, gates decide.
# ARCH REF: M4; p08 reviewer
# OWNS: Review findings
# DOES NOT OWN: Pass/fail
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (IF-12 model calls)
#   - imports from src/asf/contracts/outcomes.py: ChangeSet (input)
#   - called by src/asf/m4_execution/verification/gate.py: review_change
#   - called by tests/m4_execution/verification/test_reviewer.py: review_change
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m4_execution/verification/test_reviewer.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m4_execution/verification/reviewer.py` and `uv run mypy src/asf/m4_execution/verification/reviewer.py` are clean.

import json
import logging
from typing import Any, cast

from asf.contracts.outcomes import ChangeSet
from asf.m5_shared.gateway.gateway import ModelGateway

logger = logging.getLogger(__name__)

_MAX_DIFF_CHARS = 12000
_PROMPT = (
    "You review one code change against the interface it must implement. Report only problems that make the change "
    "wrong with respect to the contract (wrong signature, missing error case, behaviour the contract forbids). "
    "Style remarks are not findings.\n\nContract:\n{contract}\n\nFiles touched: {files}\nWorker self-report: {report}\n\n"
    "Diff:\n{diff}\n\nAnswer with a JSON list of objects {{\"blocking\": true|false, \"finding\": \"...\"}} and nothing else."
)


def _parse_findings(text: str) -> list[str]:
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end < start:
        return []
    try:
        items = json.loads(text[start : end + 1])
    except ValueError:
        logger.warning("reviewer answer was not valid JSON; no findings recorded")
        return []
    findings: list[str] = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and item.get("blocking") is True and str(item.get("finding", "")).strip():
            findings.append(str(item["finding"]).strip())
    return findings


def review_change(
    change: ChangeSet,
    capsule_lines: list[str],
    *,
    gateway: ModelGateway | None = None,
    diff_text: str = "",
) -> list[str]:
    """Return blocking findings (empty = none). Advisory only: without a gateway, or when the reviewer fails, none."""
    if gateway is None:
        return []
    prompt = _PROMPT.format(
        contract="\n".join(capsule_lines) or "(no contract lines)",
        files=", ".join(change.files_touched) or "(none)",
        report=change.self_report[:1000],
        diff=diff_text[:_MAX_DIFF_CHARS] or "(diff not provided)",
    )
    try:
        reply = gateway.model_for(cast(Any, "reviewer"), purpose="review_change").invoke(prompt)
    except Exception:  # noqa: BLE001 - the reviewer is optional and advisory; the gates decide
        logger.warning("reviewer model unavailable; the change is not reviewed", exc_info=True)
        return []
    return _parse_findings(str(getattr(reply, "content", reply)))
