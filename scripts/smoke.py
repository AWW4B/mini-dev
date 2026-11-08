# FILE: scripts/smoke.py
# ROLE: Manual smoke test for machines CI does not cover (Arch Linux): compile, header check, forbidden scan, doctor.
# ARCH REF: D-35 (Arch via manual smoke + doctor); FR-4
# OWNS: Smoke sequence
# DOES NOT OWN: Unit tests
# CONNECTS TO (external boundaries only):
#   - called by tests/scripts/test_smoke.py: main, ROOT, STEPS
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Run as `uv run python scripts/smoke.py`; paste its output into issue reports.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/scripts/test_smoke.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check scripts/smoke.py` and `uv run mypy scripts/smoke.py` are clean.

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STEPS = [
    ["-m", "compileall", "-q", "src", "scripts", "tests"],
    ["scripts/check_headers.py", "--coverage"],
    ["scripts/scan_forbidden.py"],
    ["-m", "asf", "doctor", "--output", "plain"],
]


def main() -> int:
    print(f"python {sys.version.split()[0]} on {sys.platform}; uv={'yes' if shutil.which('uv') else 'no'}")
    worst = 0
    for step in STEPS:
        rc = subprocess.run([sys.executable, *step], cwd=ROOT, check=False).returncode
        print(f"[{'ok' if rc == 0 else 'rc=' + str(rc)}] {' '.join(step)}")
        worst = max(worst, rc)
    return worst


if __name__ == "__main__":
    sys.exit(main())
