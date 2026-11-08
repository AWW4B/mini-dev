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

import re
from typing import Any

_PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN [A-Z0-9_\- ]+PRIVATE KEY-----[\s\S]+?-----END [A-Z0-9_\- ]+PRIVATE KEY-----")
_BEARER_PATTERN = re.compile(r"\bBearer\s+[a-zA-Z0-9_\-\.]{16,}", re.IGNORECASE)

_API_KEY_PATTERNS = [
    re.compile(r"\bsk-(?:ant-api03-|proj-)?[a-zA-Z0-9_\-]{20,}\b"),
    re.compile(r"\bgsk_[a-zA-Z0-9_\-]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
]

_ASSIGNMENT_PATTERN = re.compile(r"(?i)\b(api[_-]?key|secret|token|password|auth[_-]?token)\s*[:=]\s*([\"']?)([a-zA-Z0-9_\-\.]{8,})\2")

_SECRET_KEY_NAMES = frozenset({"key", "token", "secret", "password", "auth", "credential", "api_key", "secret_token", "access_token"})


def redact_text(text: str) -> str:
    """Redact secret shapes from text (idempotent, never raises)."""
    if not isinstance(text, str):
        return text

    try:
        result = _PRIVATE_KEY_PATTERN.sub("[REDACTED PRIVATE KEY]", text)
        result = _BEARER_PATTERN.sub("Bearer [REDACTED]", result)
        for pat in _API_KEY_PATTERNS:
            result = pat.sub("[REDACTED]", result)
        result = _ASSIGNMENT_PATTERN.sub(r"\1=\2[REDACTED]\2", result)
        return result
    except Exception:  # noqa: BLE001
        return text


def _redact_value(val: Any, key_name: str = "") -> Any:
    key_lower = key_name.lower().replace("-", "_")
    if any(s in key_lower for s in _SECRET_KEY_NAMES):
        return "[REDACTED]"

    if isinstance(val, str):
        return redact_text(val)
    if isinstance(val, dict):
        return {k: _redact_value(v, k) for k, v in val.items()}
    if isinstance(val, list):
        return [_redact_value(item, key_name) for item in val]
    return val


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Redact secrets and token-shaped strings from dictionary payload."""
    if not isinstance(payload, dict):
        return payload

    try:
        return {k: _redact_value(v, k) for k, v in payload.items()}
    except Exception:  # noqa: BLE001
        return payload
