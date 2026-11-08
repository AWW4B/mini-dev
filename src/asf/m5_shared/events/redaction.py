# FILE: src/asf/m5_shared/events/redaction.py
# ROLE: Redacts secrets and token-shaped strings from text and payloads before they are stored or displayed.
# ARCH REF: M5; p10; D-26; D-14b
# OWNS: Redaction rules
# DOES NOT OWN: Deciding what is secret in config (config/secrets.py)
# CONNECTS TO (external boundaries only):
#   - called by src/asf/m5_shared/events/event_log.py: redact_payload
#   - called by src/asf/m5_shared/tools/executor.py: redact_text
#   - called by src/asf/logging_setup.py: redact_text
#   - called by src/asf/web/narrative.py: redact_text
#   - called by tests/m5_shared/events/test_redaction.py: redact_text, redact_payload
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Redact API-key shapes, bearer tokens, values of environment variables named *KEY*/*TOKEN*/*SECRET*, and private-key blocks.
#   6. Redaction must be idempotent and must not raise on any input.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/events/test_redaction.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/events/redaction.py` and `uv run mypy src/asf/m5_shared/events/redaction.py` are clean.

from typing import Any


def redact_text(text: str) -> str:
    raise NotImplementedError


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError
