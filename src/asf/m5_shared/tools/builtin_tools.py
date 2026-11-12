# FILE: src/asf/m5_shared/tools/builtin_tools.py
# ROLE: Implements the built-in tools (read, write, search, run tests, run linter, list files) as plain functions registered in the ToolRegistry.
# ARCH REF: M5; p12; IF-14
# OWNS: Built-in tool behaviour
# DOES NOT OWN: Permission checks (executor/policy run before these)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/tools/registry.py: ToolRegistry (registration)
#   - imports from src/asf/platform/select.py: get_platform (platform adapter)
#   - called by src/asf/m3_orchestration/acceptance.py: run_tests
#   - called by tests/m5_shared/tools/test_builtin_tools.py: read_file, write_file, search_code, run_tests, run_linter, register_builtin_tools
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. These functions assume the executor already checked policy; they still never follow symlinks outside the given root.
#   9. Use ripgrep when available (shutil.which) and a pure-Python fallback otherwise (D-30).
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/tools/test_builtin_tools.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/tools/builtin_tools.py` and `uv run mypy src/asf/m5_shared/tools/builtin_tools.py` are clean.

import logging
import re
import shutil
from pathlib import Path
from types import SimpleNamespace

from asf.m5_shared.tools.registry import ToolRegistry
from asf.platform.select import get_platform

logger = logging.getLogger(__name__)


def read_file(root: Path, rel_path: str) -> str:
    target = get_platform().resolve_within(root, rel_path)
    return target.read_text(encoding="utf-8")


def write_file(root: Path, rel_path: str, content: str) -> None:
    target = get_platform().resolve_within(root, rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def search_code(root: Path, pattern: str, max_hits: int = 50) -> list[str]:
    rg = shutil.which("rg")
    if rg:
        try:
            res = get_platform().run_process(
                [rg, "--max-count", str(max_hits), "--no-heading", "--line-number", pattern, "."],
                cwd=root,
                timeout_s=30,
            )
            lines = res.stdout.decode("utf-8", errors="replace").splitlines()
            return lines[:max_hits]
        except Exception:  # noqa: BLE001 - ripgrep is optional (D-30): fall back to the pure Python search
            logger.debug("ripgrep search failed; using the Python fallback", exc_info=True)

    # Pure Python fallback (D-30)
    hits: list[str] = []
    try:
        rx = re.compile(pattern)
    except re.error:
        rx = re.compile(re.escape(pattern))

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(root).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if rx.search(line):
                    rel = p.relative_to(root).as_posix()
                    hits.append(f"{rel}:{lineno}: {line.strip()}")
                    if len(hits) >= max_hits:
                        return hits
        except OSError:
            logger.debug("skipping unreadable file %s", p, exc_info=True)
    return hits


def run_tests(root: Path, selectors: list[str]) -> tuple[int, str]:
    argv = ["pytest"] + selectors
    res = get_platform().run_process(argv, cwd=root, timeout_s=120)
    out = (res.stdout + res.stderr).decode("utf-8", errors="replace")
    return res.exit_code, out


def run_linter(root: Path, files: list[str]) -> tuple[int, str]:
    argv = ["ruff", "check"] + files
    res = get_platform().run_process(argv, cwd=root, timeout_s=60)
    out = (res.stdout + res.stderr).decode("utf-8", errors="replace")
    return res.exit_code, out


def register_builtin_tools(registry: ToolRegistry) -> None:
    specs = [
        (
            SimpleNamespace(
                name="read_file",
                description="Read a file from the workspace",
                args_schema={"type": "object", "properties": {"rel_path": {"type": "string"}}, "required": ["rel_path"]},
                destructive=False,
                needs_network=False,
                roles=["*"],
                source="builtin",
            ),
            lambda root, rel_path: read_file(root, rel_path),
        ),
        (
            SimpleNamespace(
                name="write_file",
                description="Write content to a file in the workspace",
                args_schema={"type": "object", "properties": {"rel_path": {"type": "string"}, "content": {"type": "string"}}, "required": ["rel_path", "content"]},
                destructive=True,
                needs_network=False,
                roles=["worker", "developer", "coder", "T2"],
                source="builtin",
            ),
            lambda root, rel_path, content: write_file(root, rel_path, content),
        ),
        (
            SimpleNamespace(
                name="search_code",
                description="Search code in the workspace matching a regex pattern",
                args_schema={"type": "object", "properties": {"pattern": {"type": "string"}, "max_hits": {"type": "integer"}}, "required": ["pattern"]},
                destructive=False,
                needs_network=False,
                roles=["*"],
                source="builtin",
            ),
            lambda root, pattern, max_hits=50: search_code(root, pattern, max_hits),
        ),
        (
            SimpleNamespace(
                name="run_tests",
                description="Run unit tests in the workspace",
                args_schema={"type": "object", "properties": {"selectors": {"type": "array", "items": {"type": "string"}}}, "required": ["selectors"]},
                destructive=False,
                needs_network=False,
                roles=["worker", "reviewer", "acceptance"],
                source="builtin",
            ),
            lambda root, selectors: run_tests(root, selectors),
        ),
        (
            SimpleNamespace(
                name="run_linter",
                description="Run linter in the workspace",
                args_schema={"type": "object", "properties": {"files": {"type": "array", "items": {"type": "string"}}}, "required": ["files"]},
                destructive=False,
                needs_network=False,
                roles=["worker", "reviewer"],
                source="builtin",
            ),
            lambda root, files: run_linter(root, files),
        ),
    ]

    for spec, fn in specs:
        registry.register(spec, fn)  # type: ignore[arg-type]
