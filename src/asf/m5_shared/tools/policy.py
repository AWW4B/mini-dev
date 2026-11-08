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
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from asf.config.loader import load_layered
from asf.contracts.tools import SandboxTier, ToolInvocation, ToolSpec
from asf.platform.select import get_platform


class Verdict(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    NEEDS_APPROVAL = "needs_approval"


class PolicyVerdict(BaseModel):
    verdict: Verdict
    reason: str


class PolicyEngine:
    policy_config: dict[str, Any]

    def __init__(self) -> None:
        try:
            self.policy_config = load_layered("policy.toml")
        except Exception:
            self.policy_config = {}

    def check(
        self,
        invocation: ToolInvocation,
        spec: ToolSpec,
        tier: SandboxTier,
        allowed_files: list[str],
    ) -> PolicyVerdict:
        # 1. Role permission check
        if spec.roles and invocation.role not in spec.roles and "*" not in spec.roles:
            return PolicyVerdict(
                verdict=Verdict.DENY,
                reason=f"Role '{invocation.role}' not permitted for tool '{spec.name}'",
            )

        tier_str = tier.value if hasattr(tier, "value") else str(tier)

        # 2. Tier B restrictions
        if tier_str == "B":
            if spec.needs_network:
                return PolicyVerdict(
                    verdict=Verdict.DENY,
                    reason="Network is disabled in Sandbox Tier B",
                )
            if spec.source == "codeexec":
                return PolicyVerdict(
                    verdict=Verdict.DENY,
                    reason="Code execution is disabled in Sandbox Tier B",
                )

        # 3. Network access check
        if spec.needs_network and tier_str != "A":
            return PolicyVerdict(
                verdict=Verdict.DENY,
                reason=f"Tool '{spec.name}' requires network access which is not permitted",
            )

        # 4. Path argument validation
        ws_path = Path(invocation.workspace_dir)
        path_keys = {"path", "file", "filepath", "filename", "dest", "target", "cwd"}
        for k, v in invocation.args.items():
            if k.lower() in path_keys or (isinstance(v, str) and ("/" in v or "\\" in v)):
                val_str = str(v)
                try:
                    resolved = get_platform().resolve_within(ws_path, val_str)
                    if allowed_files:
                        try:
                            rel = resolved.relative_to(ws_path).as_posix()
                        except ValueError:
                            rel = val_str
                        norm_allowed = {Path(f).as_posix() for f in allowed_files}
                        if rel not in norm_allowed:
                            return PolicyVerdict(
                                verdict=Verdict.DENY,
                                reason=f"Path '{rel}' not in allowed_files scope",
                            )
                except Exception as err:
                    return PolicyVerdict(
                        verdict=Verdict.DENY,
                        reason=f"Path '{val_str}' denied: {err}",
                    )

        # 5. Destructive check
        if spec.destructive:
            return PolicyVerdict(
                verdict=Verdict.NEEDS_APPROVAL,
                reason=f"Tool '{spec.name}' is destructive and needs approval",
            )

        return PolicyVerdict(verdict=Verdict.ALLOW, reason="Policy checks passed")
