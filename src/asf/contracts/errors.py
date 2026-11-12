# FILE: src/asf/contracts/errors.py
# ROLE: Defines the exception hierarchy every module uses to report failures to its caller.
# ARCH REF: p16 failure matrix; all modules
# OWNS: Exception classes and their meaning
# DOES NOT OWN: Error handling policy (owned by each caller)
# CONNECTS TO (external boundaries only):
#   - called by src/asf/m5_shared/state_store/store.py: StateConflict
#   - called by src/asf/m5_shared/gateway/gateway.py: BudgetExceeded, ProviderUnavailable
#   - called by src/asf/m5_shared/runtime/local_runtime.py: AsfError
#   - called by src/asf/m5_shared/tools/executor.py: PolicyDenied, ApprovalRequired, SandboxUnavailable
#   - called by src/asf/m5_shared/tools/codeexec/runner.py: SandboxUnavailable
#   - called by src/asf/m5_shared/context/context_service.py: ContextOverflow
#   - called by src/asf/platform/linux.py: PolicyDenied
#   - called by src/asf/platform/windows.py: PolicyDenied
#   - called by src/asf/platform/fallback.py: SandboxUnavailable
#   - called by src/asf/config/settings.py: ConfigError
#   - called by src/asf/m3_orchestration/lifecycle.py: StateConflict
#   - called by src/asf/web/server.py: PolicyDenied
#   - called by src/asf/m2_request/document_ingestion.py: ApprovalRequired
#   - called by src/asf/m2_request/pipeline.py: PolicyDenied
#   - called by tests/contracts/test_errors.py: AsfError, ConfigError, PolicyDenied, ApprovalRequired, BudgetExceeded, ContextOverflow, ProviderUnavailable, InvalidModelOutput, SandboxUnavailable, StateConflict, NotSupportedOnPlatform
#   - called by tests/web/test_server.py: PolicyDenied
#   - called by src/asf/m5_shared/state_store/recovery.py: AsfError
#   - called by src/asf/config/loader.py: ConfigError
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. This file is declarations only: Pydantic models, enums and type aliases. Add field validators only where the docstring of a field states a constraint.
#   6. Every model must round-trip through model_dump_json() / model_validate_json() unchanged; the JSON Schema exported from these models is the published contract (D-39: no hand-written JSON).
#   7. Changing a field name or type is a contract change: stop and report instead.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; business logic; I/O; imports from asf.m1-m5 packages, asf.cli, asf.web or asf.platform
# ERRORS: Not applicable (this file defines the errors).
# DONE WHEN: (1) tests/contracts/test_errors.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/contracts/errors.py` and `uv run mypy src/asf/contracts/errors.py` are clean.

class AsfError(Exception):
    """Base class for every error raised by asf code."""


class ConfigError(AsfError):
    """Configuration is missing, invalid or contradictory (D-37)."""


class PolicyDenied(AsfError):
    """The ToolExecutor or a policy refused an action (p12, D-16)."""


class ApprovalRequired(AsfError):
    """The action needs a human decision through the Decision Broker (IF-03)."""


class BudgetExceeded(AsfError):
    """A RunBudget limit (tokens, spend, wall-clock, nodes) is exhausted (p06)."""


class ContextOverflow(AsfError):
    """Must-have context does not fit the token budget; caller must re-split (p12, p05)."""


class ProviderUnavailable(AsfError):
    """No model route in the fallback chain is usable (p11)."""


class InvalidModelOutput(AsfError):
    """Model output failed schema validation after the allowed re-asks (p11)."""


class SandboxUnavailable(AsfError):
    """The required sandbox tier is not available on this machine (D-20, D-21)."""


class StateConflict(AsfError):
    """Optimistic-concurrency check failed in the State Store; reload and retry (p09)."""


class NotSupportedOnPlatform(AsfError):
    """The requested OS capability does not exist on this platform (platform adapter)."""
