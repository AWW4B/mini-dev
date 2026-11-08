# FILE: src/asf/m5_shared/tools/policy.py
# ROLE: Decides allow / deny / needs-approval for a tool invocation from role, path scope, network and destructiveness.
# ARCH REF: M5; p12; D-16; D-18 per-server policy; D-21; D-22
# OWNS: Policy evaluation, path-scope resolution
# DOES NOT OWN: Executing tools
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tools.py: ToolInvocation, ToolSpec, SandboxTier (inputs)
#   - imports from src/asf/platform/select.py: get_platform (platform adapter)
#   - imports from src/asf/config/loader.py: load_layered (policy.toml)
#   - called by src/asf/m5_shared/tools/executor.py: PolicyEngine, Verdict
#   - called by tests/m5_shared/tools/test_policy.py: Verdict, PolicyVerdict, PolicyEngine
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Resolve every path argument with the platform adapter (real path, symlink and Windows junction escapes rejected) and require it inside allowed_files or the task worktree.
#   9. needs_network tools are denied unless the dependency-install step was approved (D-22); tier B disables network and code_exec entirely.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/tools/test_policy.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/tools/policy.py` and `uv run mypy src/asf/m5_shared/tools/policy.py` are clean.

from enum import StrEnum

from pydantic import BaseModel

from asf.contracts.tools import SandboxTier, ToolInvocation, ToolSpec


class Verdict(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    NEEDS_APPROVAL = "needs_approval"


class PolicyVerdict(BaseModel):
    verdict: Verdict
    reason: str


class PolicyEngine:
    def check(self, invocation: ToolInvocation, spec: ToolSpec, tier: SandboxTier, allowed_files: list[str]) -> PolicyVerdict:
        raise NotImplementedError
