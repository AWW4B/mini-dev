# FILE: src/asf/m4_execution/verification/failure_classifier.py
# ROLE: Classifies gate failures: rules over logs first, T1 only when no rule matches.
# ARCH REF: M4; p08 classify failure; D-09 tiny-model tasks
# OWNS: Failure classification
# DOES NOT OWN: Routing (gate)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/outcomes.py: FailureClass (classes)
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (IF-12 model calls)
#   - called by src/asf/m4_execution/verification/gate.py: classify_failure
#   - called by tests/m4_execution/verification/test_failure_classifier.py: classify_failure
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m4_execution/verification/test_failure_classifier.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m4_execution/verification/failure_classifier.py` and `uv run mypy src/asf/m4_execution/verification/failure_classifier.py` are clean.

import logging
import re
from typing import Any, cast

from asf.contracts.outcomes import FailureClass
from asf.m5_shared.gateway.gateway import ModelGateway

logger = logging.getLogger(__name__)

# Ordered: the first matching rule wins, so the most specific / least ambiguous classes come first.
_RULES: list[tuple[FailureClass, re.Pattern[str]]] = [
    (FailureClass.POLICY_VIOLATION, re.compile(r"POLICY_VIOLATION|PolicyDenied|denied by policy|policy violation", re.I)),
    (FailureClass.CONTEXT_OVERFLOW, re.compile(r"CONTEXT_OVERFLOW|ContextOverflow|context (length|window)|maximum context|too many tokens", re.I)),
    (FailureClass.SPEC_TOO_LARGE, re.compile(r"SPEC_TOO_LARGE|step budget (was )?(exhausted|spent)|output (was )?truncated|finish_reason\W+length|max_tokens (reached|exceeded)", re.I)),
    (
        FailureClass.ENV_INFRA,
        re.compile(
            r"No space left on device|ENOSPC|Read-only file system|Connection refused|Name or service not known|"
            r"Temporary failure in name resolution|ProxyError|Max retries exceeded|sandbox (is )?unavailable|"
            r"SandboxUnavailable|command not found|is not recognized as an internal or external command|"
            r"executable file not found|uv: not found",
            re.I,
        ),
    ),
    (FailureClass.CONTRACT_GAP, re.compile(r"CONTRACT_GAP|missing (from the )?contract|no contract for", re.I)),
    (
        FailureClass.CONTRACT_MISMATCH,
        re.compile(
            r"CONTRACT_MISMATCH|contract test.*(FAILED|failed)|(FAILED|ERROR)\s+\S*contracts?[/\\]|"
            r"unexpected keyword argument|got an unexpected keyword|takes \d+ positional arguments? but \d+ (was|were) given|"
            r"missing \d+ required positional arguments?",
            re.I,
        ),
    ),
    (FailureClass.FLAKY, re.compile(r"\bflaky\b|intermittent|ReadTimeout|timed out waiting|Timeout(Error)? waiting", re.I)),
]

_LOCAL_BUG_MARKERS = re.compile(r"AssertionError|FAILED|Error\b|error:|Traceback|assert ", re.I)

_PROMPT = (
    "Classify this failed test or static-check log into exactly one class and answer with the class name only.\n"
    "Classes: LOCAL_BUG (the new code is wrong), FLAKY (nondeterministic or timing), ENV_INFRA (tooling, network, disk), "
    "CONTRACT_MISMATCH (disagrees with a declared interface), SPEC_TOO_LARGE (the task is too big for one attempt).\n\n"
    "Log (tail):\n{log}"
)
_MODEL_CLASSES = (
    FailureClass.LOCAL_BUG,
    FailureClass.FLAKY,
    FailureClass.ENV_INFRA,
    FailureClass.CONTRACT_MISMATCH,
    FailureClass.SPEC_TOO_LARGE,
)
_LOG_TAIL_CHARS = 4000


def _classify_with_model(log_text: str, gateway: ModelGateway) -> FailureClass | None:
    try:
        model = gateway.model_for(cast(Any, "T1"), purpose="classify_failure")
        reply = model.invoke(_PROMPT.format(log=log_text[-_LOG_TAIL_CHARS:]))
    except Exception:  # noqa: BLE001 - the tiny model is optional; the rule default below applies
        logger.warning("T1 failure classification unavailable; using the rule default", exc_info=True)
        return None
    answer = str(getattr(reply, "content", reply)).upper()
    for failure_class in _MODEL_CLASSES:
        if failure_class.value in answer:
            return failure_class
    return None


def classify_failure(log_text: str, *, gateway: ModelGateway | None = None) -> FailureClass:
    """Rules over the log first; the tiny model (T1) only when no rule matches and a gateway is given."""
    for failure_class, pattern in _RULES:
        if pattern.search(log_text):
            return failure_class
    if gateway is not None and log_text.strip():
        modelled = _classify_with_model(log_text, gateway)
        if modelled is not None:
            return modelled
    return FailureClass.LOCAL_BUG
