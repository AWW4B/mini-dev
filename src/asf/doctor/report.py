# FILE: src/asf/doctor/report.py
# ROLE: Writes the doctor report (Markdown + JSON) to the log dir and computes the exit code.
# ARCH REF: FR-4 doctor report; D-45
# OWNS: Report files and exit code (0 ok, 1 warnings, 2 failures)
# DOES NOT OWN: Running checks
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/doctor/checks.py: CheckResult, CheckStatus (results)
#   - imports from src/asf/config/paths.py: AppPaths, get_paths (cross-platform base directories)
#   - called by src/asf/cli/commands/doctor.py: write_report, exit_code_for
#   - called by tests/doctor/test_report.py: write_report, exit_code_for
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/doctor/test_report.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/doctor/report.py` and `uv run mypy src/asf/doctor/report.py` are clean.

import json
from pathlib import Path

from asf.config.paths import AppPaths, get_paths  # noqa: F401
from asf.doctor.checks import CheckResult, CheckStatus


def write_report(results: list[CheckResult], dest_dir: Path | None = None) -> tuple[Path, Path]:
    target_dir = dest_dir or get_paths().log_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    md_path = target_dir / "doctor_report.md"
    json_path = target_dir / "doctor_report.json"

    # Write JSON report
    data = [r.model_dump() for r in results]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Write Markdown report
    lines: list[str] = [
        "# AI Software Factory — Doctor Report",
        "",
        "| Check | Status | Details |",
        "|---|---|---|",
    ]
    for r in results:
        status_str = getattr(r.status, "value", str(r.status)).upper()
        lines.append(f"| `{r.name}` | **{status_str}** | {r.detail} |")

    # Add fix hints if any
    hints: list[str] = []
    for r in results:
        if r.fix_hints:
            hints.append(f"### `{r.name}`")
            for distro, cmd in r.fix_hints.items():
                hints.append(f"- **{distro}**: `{cmd}`")
            hints.append("")

    if hints:
        lines.extend(["", "## Fix Hints", ""])
        lines.extend(hints)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return md_path, json_path


def exit_code_for(results: list[CheckResult]) -> int:
    has_warn = False
    for r in results:
        status_val = getattr(r.status, "value", str(r.status))
        if status_val == CheckStatus.FAIL.value or status_val == "fail":
            return 2
        if status_val == CheckStatus.WARN.value or status_val == "warn":
            has_warn = True
    return 1 if has_warn else 0
