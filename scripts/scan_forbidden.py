# FILE: scripts/scan_forbidden.py
# ROLE: Scans the repository for container-runtime references, hardcoded OS paths and drive letters, shell=True, os.system and shell-specific invocations.
# ARCH REF: FR-3 (no containers); FR-4 (cross-platform); Phase 2 validation
# OWNS: Forbidden-pattern rules
# DOES NOT OWN: Fixing hits
# CONNECTS TO (external boundaries only):
#   - called by .github/workflows/ci.yml: main
#   - called by tests/scripts/test_scan_forbidden.py: body_without_header, main, ROOT, SKIP_DIRS, SKIP_FILES, ANYWHERE, CODE_ONLY
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Use only the standard library.
#   9. Build patterns by string concatenation so this file never matches itself.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) `uv run python scripts/scan_forbidden.py` exits 0 on the repository. (2) tests/scripts/test_scan_forbidden.py passes on Windows and Linux. (3) `uv run python scripts/check_headers.py` reports no problem for this file. (4) `uv run ruff check scripts/scan_forbidden.py` and `uv run mypy scripts/scan_forbidden.py` are clean.

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
SKIP_FILES = {"uv.lock", "requirements.lock.txt", "AI_Software_Factory_Research_and_Decisions.md"}  # research doc compares sandbox options by name
# patterns are assembled from pieces so this file does not match itself
ANYWHERE = [
    ("container runtime reference", re.compile("dock" + "er|podm" + "an", re.I)),
    ("hardcoded system directory", re.compile(r"(?<![\w.:/-])/(?:" + "tm" + "p|ho" + "me|us" + "r|et" + "c|va" + "r|op" + "t)/")),
    ("hardcoded drive letter", re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:\\" + r"\\?[A-Za-z]")),
]
CODE_ONLY = [
    ("shell=True", re.compile("shell" + r"\s*=\s*" + "True")),
    ("os.system", re.compile(r"\bos\." + "system" + r"\s*\(")),
    ("PowerShell-only invocation", re.compile(r"[\"'](?:power" + r"shell|pw" + r"sh)[\"']", re.I)),
    ("bash-only invocation", re.compile(r"[\"'](?:ba" + r"sh|/bin/s" + r"h)[\"']")),
]


def body_without_header(text: str) -> str:
    lines = text.splitlines()
    i = 0
    while i < len(lines) and lines[i].startswith("#"):
        i += 1
    return "\n".join(lines[i:])


def main() -> int:
    hits: list[str] = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or set(p.relative_to(ROOT).parts) & SKIP_DIRS or p.name in SKIP_FILES or p.suffix in {".pyc", ".zip", ".gguf"}:
            continue
        if p.resolve() == Path(__file__).resolve():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        rel = p.relative_to(ROOT).as_posix()
        for label, rx in ANYWHERE:
            for m in rx.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                hits.append(f"{rel}:{line}: {label}: {m.group(0)!r}")
        if p.suffix == ".py":
            code = body_without_header(text)
            for label, rx in CODE_ONLY:
                for m in rx.finditer(code):
                    hits.append(f"{rel}: {label}: {m.group(0)!r}")
    for h in hits:
        print(f"FORBIDDEN: {h}")
    print(f"scan_forbidden: {len(hits)} hit(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
