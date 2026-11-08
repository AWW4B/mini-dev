# FILE: src/asf/m5_shared/tools/skills.py
# ROLE: Indexes Agent Skills folders and serves metadata first, full body on demand (IF-23).
# ARCH REF: M5; p12 Skills; IF-23 SkillLookup; D-17
# OWNS: Skill discovery, validation (including size warning), loading
# DOES NOT OWN: Writing skills
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tools.py: SkillManifest (IF-23)
#   - imports from src/asf/config/paths.py: AppPaths, get_paths (cross-platform base directories)
#   - called by src/asf/m2_request/request_understanding.py: SkillsRegistry
#   - called by src/asf/m3_orchestration/planning/test_authoring.py: SkillsRegistry
#   - called by src/asf/m3_orchestration/decomposition/splitter.py: SkillsRegistry
#   - called by src/asf/cli/commands/skills.py: SkillsRegistry
#   - called by tests/m5_shared/tools/test_skills.py: SkillsRegistry
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Parse YAML frontmatter (name, description, version, allowed-tools); warn when a body exceeds the configured size.
#   9. Use these Agent Skills (load via SkillsRegistry): skills/request-structuring/SKILL.md, skills/split-proposal/SKILL.md, skills/write-tests-from-acceptance/SKILL.md, skills/python-module-from-contract/SKILL.md, skills/reproduce-bug-as-failing-test/SKILL.md, skills/characterisation-tests/SKILL.md.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/tools/test_skills.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/tools/skills.py` and `uv run mypy src/asf/m5_shared/tools/skills.py` are clean.

from asf.contracts.tools import SkillManifest


class SkillsRegistry:
    def lookup(self, capability: str, role: str) -> list[SkillManifest]:
        raise NotImplementedError

    def load_body(self, name: str) -> str:
        raise NotImplementedError

    def validate_all(self) -> list[str]:
        """Return problems and size warnings (empty list = valid)."""
        raise NotImplementedError
