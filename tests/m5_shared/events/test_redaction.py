# FILE: tests/m5_shared/events/test_redaction.py
# ROLE: Tests that prove src/asf/m5_shared/events/redaction.py meets its DONE WHEN conditions.
# ARCH REF: M5; p10; D-26; D-14b; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/events/redaction.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/events/redaction.py: redact_text, redact_payload (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/events/test_redaction.py` on Windows and Linux once src/asf/m5_shared/events/redaction.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/events/test_redaction.py` and `uv run mypy tests/m5_shared/events/test_redaction.py` are clean.


from asf.m5_shared.events.redaction import redact_payload, redact_text


def test_redact_text_meets_contract() -> None:
    """Prove redact_text behaves as declared in src/asf/m5_shared/events/redaction.py."""
    # API key shapes
    openai_key = "sk-1234567890abcdef1234567890abcdef"
    text_with_key = f"Connecting using key={openai_key} now"
    redacted = redact_text(text_with_key)
    assert openai_key not in redacted
    assert "[REDACTED]" in redacted

    # Anthropic key shape
    anthropic_key = "sk-ant-api03-1234567890abcdef1234567890"
    redacted_ant = redact_text(f"Key: {anthropic_key}")
    assert anthropic_key not in redacted_ant
    assert "[REDACTED]" in redacted_ant

    # Bearer token
    bearer = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abcdef1234567890"
    redacted_bearer = redact_text(f"Authorization: {bearer}")
    assert "eyJhbGciOi" not in redacted_bearer

    # Private key block
    pkey = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----"
    redacted_pkey = redact_text(f"Certificate: {pkey}")
    assert "MIIEowIBAAK" not in redacted_pkey
    assert "[REDACTED" in redacted_pkey

    # Idempotent
    assert redact_text(redacted) == redacted
    assert redact_text("regular safe text") == "regular safe text"


def test_redact_payload_meets_contract() -> None:
    """Prove redact_payload behaves as declared in src/asf/m5_shared/events/redaction.py."""
    payload = {
        "user": "alice",
        "api_key": "raw_secret_value_12345",
        "nested": {
            "SECRET_TOKEN": "top_secret_token",
            "message": "Used sk-abcdef123456789012345678 to authenticate",
            "items": ["safe", "another_password: super_secret_12345"],
        },
    }
    redacted = redact_payload(payload)
    assert redacted["user"] == "alice"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["SECRET_TOKEN"] == "[REDACTED]"  # noqa: S105
    assert "sk-abcdef" not in redacted["nested"]["message"]

    # Original payload not mutated
    assert payload["api_key"] == "raw_secret_value_12345"

    # Idempotent
    assert redact_payload(redacted) == redacted
