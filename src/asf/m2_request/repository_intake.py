# FILE: src/asf/m2_request/repository_intake.py
# ROLE: Snapshots a repository into the managed workspace and builds its RepoProfile (languages, build/test commands, baseline).
# ARCH REF: M2; p03 Repository Intake; D-29 (git subprocess + intake_rules.toml; v1 Python)
# OWNS: Repo snapshot, detection, baseline run
# DOES NOT OWN: Index queries during work (context/repo_index.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/requests.py: RepoProfile (output)
#   - imports from src/asf/m5_shared/workspace/workspace.py: Workspace (IF-15 git operations)
#   - imports from src/asf/m5_shared/context/repo_index.py: RepoIndex (static index)
#   - imports from src/asf/platform/select.py: get_platform (platform adapter)
#   - imports from src/asf/platform/base.py: SandboxSpec (sandboxed baseline run)
#   - imports from src/asf/config/loader.py: load_layered (intake_rules.toml)
#   - called by src/asf/m2_request/pipeline.py: intake_repository
#   - called by tests/m2_request/test_repository_intake.py: intake_repository
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Build and test commands are argument lists; detection is deterministic (pyproject, setup.cfg, pytest config).
#   9. Run the baseline tests in the sandbox through the platform adapter; record pass/fail lists.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m2_request/test_repository_intake.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m2_request/repository_intake.py` and `uv run mypy src/asf/m2_request/repository_intake.py` are clean.

import logging
import os
import sys
from pathlib import Path

from asf.config.loader import load_layered
from asf.contracts.requests import RepoProfile
from asf.m5_shared.context.repo_index import RepoIndex
from asf.m5_shared.workspace.workspace import Workspace  # noqa: F401
from asf.platform.base import SandboxSpec
from asf.platform.select import get_platform

logger = logging.getLogger(__name__)

_SKIP_DIRS = frozenset({".git", ".venv", "venv", "__pycache__", "node_modules", ".mypy_cache", ".ruff_cache", ".pytest_cache", "dist", "build"})
_LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
}
_BASELINE_TIMEOUT_S = 30


def _detect_languages(repo_path: Path) -> list[str]:
    """Languages by file suffix; skipped directories are pruned before they are walked."""
    found: set[str] = set()
    for _dirpath, dirnames, filenames in os.walk(repo_path):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            language = _LANGUAGE_BY_SUFFIX.get(Path(name).suffix)
            if language is not None:
                found.add(language)
    return sorted(found)


def _run_baseline(repo_path: Path, test_command: list[str]) -> tuple[list[str], list[str]]:
    """Run the baseline tests in a real sandbox (tier A); without one the repository's code is not executed."""
    backend = get_platform().sandbox()
    tier = getattr(backend.tier, "value", backend.tier)
    if tier != "A" or not backend.available():
        logger.warning("baseline tests not run: no tier-A sandbox available (tier %s); the repository's code is not executed unsandboxed", tier)
        return [], []
    spec = SandboxSpec(
        argv=test_command,
        cwd=repo_path,
        writable_paths=[repo_path],
        readable_paths=[repo_path],
        network=False,
        timeout_s=_BASELINE_TIMEOUT_S,
    )
    result = backend.run(spec)
    if result.timed_out:
        return [], ["baseline_timeout"]
    if result.exit_code == 0:
        return ["all_tests"], []
    return [], ["some_tests_failed"]


def intake_repository(repo_ref: str, project_id: str) -> RepoProfile:
    repo_path = Path(repo_ref)
    if not repo_path.is_dir():
        return RepoProfile(
            languages=[],
            build_commands=[],
            test_commands=[],
            baseline_passed=[],
            baseline_failed=[],
            supported=False,
        )

    # 1. Intake rules (a corrupt config file raises ConfigError instead of being ignored)
    rules = load_layered("intake_rules")
    supported_langs = list(rules.get("supported_languages", ["python"]))

    # 2. Detect languages
    languages = _detect_languages(repo_path)
    supported = any(lang in supported_langs for lang in languages) if languages else True

    # 3. Detect build & test commands
    build_commands: list[list[str]] = []
    test_commands: list[list[str]] = []

    if (repo_path / "pyproject.toml").is_file():
        build_commands.append(["uv", "sync"])
        test_commands.append(["uv", "run", "pytest"])
    elif (repo_path / "setup.cfg").is_file() or (repo_path / "setup.py").is_file():
        build_commands.append([sys.executable, "-m", "pip", "install", "-e", "."])
        test_commands.append([sys.executable, "-m", "pytest"])
    elif any(repo_path.glob("test_*.py")) or (repo_path / "tests").is_dir():
        test_commands.append([sys.executable, "-m", "pytest"])

    # 4. Build static index
    index = RepoIndex()
    index.build(repo_path)
    index_ref = f"index:{project_id}"

    # 5. Baseline test run
    baseline_passed, baseline_failed = _run_baseline(repo_path, test_commands[0]) if test_commands else ([], [])

    return RepoProfile(
        languages=languages,
        build_commands=build_commands,
        test_commands=test_commands,
        baseline_passed=baseline_passed,
        baseline_failed=baseline_failed,
        index_ref=index_ref,
        supported=supported,
    )
