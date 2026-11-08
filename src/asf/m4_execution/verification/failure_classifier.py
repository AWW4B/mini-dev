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

from asf.contracts.outcomes import FailureClass


def classify_failure(log_text: str) -> FailureClass:
    raise NotImplementedError
