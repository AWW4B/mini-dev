# FILE: src/asf/config/secrets.py
# ROLE: Looks up provider API keys: keyring first, then FACTORY_<PROVIDER>_API_KEY, then a .env in the user config dir.
# ARCH REF: D-38
# OWNS: Key lookup and the key-source report for doctor
# DOES NOT OWN: Storing keys in TOML (forbidden)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/paths.py: AppPaths, get_paths (cross-platform base directories)
#   - called by src/asf/m5_shared/gateway/providers.py: get_api_key
#   - called by src/asf/doctor/checks.py: key_sources
#   - called by tests/config/test_secrets.py: get_api_key, key_sources
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Warn (do not fail) when the .env file is readable by other users on Linux.
#   9. Never return keys in reports; report only the source name.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; writing keys to logs, events, TOML or the sandbox environment
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/config/test_secrets.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/config/secrets.py` and `uv run mypy src/asf/config/secrets.py` are clean.

def get_api_key(provider: str) -> str | None:
    raise NotImplementedError


def key_sources() -> dict[str, str]:
    """Map provider -> 'keyring' | 'env' | 'dotenv' | 'missing' (never the key itself)."""
    raise NotImplementedError
