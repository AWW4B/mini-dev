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

import logging
from pathlib import Path
from typing import Any

from asf.config.paths import AppPaths, get_paths  # noqa: F401
from asf.contracts.tools import SkillManifest

logger = logging.getLogger(__name__)


def _parse_skill_file(skill_path: Path) -> tuple[dict[str, Any], str, int]:
    text = skill_path.read_text(encoding="utf-8")
    frontmatter: dict[str, Any] = {}
    body = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            body = parts[2].lstrip("\n")
            for line in fm_text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                k, _, v = line.partition(":")
                k = k.strip()
                v = v.strip()
                if v.startswith("[") and v.endswith("]"):
                    items = [x.strip() for x in v[1:-1].split(",") if x.strip()]
                    frontmatter[k] = items
                else:
                    frontmatter[k] = v.strip("\"'")

    return frontmatter, body, len(body)


class SkillsRegistry:
    skills_dir: Path
    _manifests: dict[str, SkillManifest]
    _bodies: dict[str, str]

    def __init__(self, skills_dir: Path | None = None) -> None:
        if skills_dir is not None:
            self.skills_dir = skills_dir
        else:
            repo_skills = Path(__file__).resolve().parents[4] / "skills"
            if repo_skills.is_dir():
                self.skills_dir = repo_skills
            else:
                data_skills = get_paths().data_dir / "skills"
                self.skills_dir = data_skills if data_skills.is_dir() else Path.cwd() / "skills"
        self._manifests = {}
        self._bodies = {}
        self._index()

    def _index(self) -> None:
        if not self.skills_dir.is_dir():
            return

        for p in sorted(self.skills_dir.rglob("SKILL.md")):
            try:
                fm, body, chars = _parse_skill_file(p)
                name = str(fm.get("name", p.parent.name))
                desc = str(fm.get("description", ""))
                version = str(fm.get("version", "0.0.1"))
                allowed = list(fm.get("allowed-tools", []))
                manifest = SkillManifest(
                    name=name,
                    description=desc,
                    version=version,
                    allowed_tools=allowed,
                    path=p.as_posix(),
                    body_chars=chars,
                )
                self._manifests[name] = manifest
                self._bodies[name] = body
            except Exception:  # noqa: BLE001 - one malformed skill must not hide the others
                logger.warning("skipping skill %s: it could not be indexed", p, exc_info=True)

    def lookup(self, capability: str, role: str) -> list[SkillManifest]:
        cap_lower = capability.lower().strip()
        if not cap_lower or cap_lower == "*":
            return list(self._manifests.values())

        matched: list[SkillManifest] = []
        for m in self._manifests.values():
            if cap_lower in m.name.lower() or cap_lower in m.description.lower():
                matched.append(m)
        return matched

    def load_body(self, name: str) -> str:
        if name not in self._bodies:
            raise KeyError(f"Skill '{name}' not found in registry")
        return self._bodies[name]

    def validate_all(self) -> list[str]:
        """Return problems and size warnings (empty list = valid)."""
        warnings: list[str] = []
        for name, manifest in self._manifests.items():
            if not manifest.name:
                warnings.append(f"Skill at '{manifest.path}' missing 'name' in frontmatter")
            if not manifest.description:
                warnings.append(f"Skill '{name}' missing 'description' in frontmatter")
            body = self._bodies.get(name, "")
            line_count = len(body.splitlines())
            if line_count > 400:
                warnings.append(f"Skill '{name}' body exceeds 400 lines ({line_count} lines)")
        return warnings
