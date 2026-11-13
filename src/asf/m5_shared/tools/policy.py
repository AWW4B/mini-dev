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


_PATH_KEYS = frozenset({"path", "rel_path", "file", "filepath", "filename", "dest", "target", "cwd"})
_PATH_LIST_KEYS = frozenset({"files", "paths", "selectors"})


def _path_arguments(args: dict[str, Any]) -> list[str]:
    """The arguments that name paths: by key only. File contents and free text are never mistaken for paths."""
    paths: list[str] = []
    for key, value in args.items():
        lowered = key.lower()
        if lowered in _PATH_KEYS and isinstance(value, str):
            paths.append(value)
        elif lowered in _PATH_LIST_KEYS and isinstance(value, list):
            paths.extend(str(item).split("::", 1)[0] for item in value if isinstance(item, str))  # test ids: tests/x.py::name
    return paths


class PolicyEngine:
    policy_config: dict[str, Any]

    def __init__(self) -> None:
        self.policy_config = load_layered("policy")  # a broken policy file raises ConfigError (fail closed)

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
        norm_allowed = {Path(f).as_posix() for f in allowed_files}
        scope_enforced = False
        for candidate in _path_arguments(invocation.args):
            try:
                resolved = get_platform().resolve_within(ws_path, candidate)  # never outside the workspace, never through a link
            except Exception as err:  # noqa: BLE001 - the platform adapter raises PolicyDenied or OS errors; both mean deny
                return PolicyVerdict(verdict=Verdict.DENY, reason=f"Path '{candidate}' denied: {err}")
            if spec.destructive and allowed_files:
                # Changing a file is limited to the task's own files. Reading is limited to the workspace only: a worker
                # must be able to read its tests, its read-only files and the code it depends on.
                try:
                    rel = resolved.relative_to(ws_path).as_posix()
                except ValueError:
                    rel = candidate
                if rel not in norm_allowed:
                    return PolicyVerdict(verdict=Verdict.DENY, reason=f"Path '{rel}' not in allowed_files scope")
                scope_enforced = True

        # 5. Destructive check: a destructive tool that stayed inside the task's files is the worker's normal job; a destructive
        # tool with no path scope to check (delete anything, run anything) needs a person's approval.
        if spec.destructive and not scope_enforced:
            return PolicyVerdict(
                verdict=Verdict.NEEDS_APPROVAL,
                reason=f"Tool '{spec.name}' is destructive and needs approval",
            )

        return PolicyVerdict(verdict=Verdict.ALLOW, reason="Policy checks passed")
