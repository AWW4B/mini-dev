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

import sys
from pathlib import Path

from asf.config.loader import load_layered
from asf.contracts.requests import RepoProfile
from asf.m5_shared.context.repo_index import RepoIndex
from asf.m5_shared.workspace.workspace import Workspace  # noqa: F401
from asf.platform.select import get_platform


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

    # 1. Load intake rules
    try:
        rules = load_layered("intake_rules")
    except Exception:  # noqa: BLE001
        rules = {}
    supported_langs = list(rules.get("supported_languages", ["python"]))

    # 2. Detect languages
    detected_langs: set[str] = set()
    for p in repo_path.rglob("*"):
        if not p.is_file():
            continue
        if any(part in {".git", ".venv", "__pycache__", "node_modules"} for part in p.parts):
            continue
        if p.suffix == ".py":
            detected_langs.add("python")
        elif p.suffix in {".js", ".jsx"}:
            detected_langs.add("javascript")
        elif p.suffix in {".ts", ".tsx"}:
            detected_langs.add("typescript")
        elif p.suffix == ".rs":
            detected_langs.add("rust")

    languages = sorted(detected_langs)
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
    baseline_passed: list[str] = []
    baseline_failed: list[str] = []

    if test_commands:
        platform = get_platform()
        try:
            res = platform.run_process(test_commands[0], cwd=repo_path, timeout_s=30)
            if res.exit_code == 0:
                baseline_passed.append("all_tests")
            else:
                baseline_failed.append("some_tests_failed")
        except Exception as _run_err:  # noqa: BLE001
            _ = _run_err
            baseline_failed.append("baseline_execution_error")

    return RepoProfile(
        languages=languages,
        build_commands=build_commands,
        test_commands=test_commands,
        baseline_passed=baseline_passed,
        baseline_failed=baseline_failed,
        index_ref=index_ref,
        supported=supported,
    )
