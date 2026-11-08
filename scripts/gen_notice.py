# FILE: scripts/gen_notice.py
# ROLE: Regenerates the third-party licence list from uv.lock plus installed package metadata, flagging copyleft and proprietary terms.
# ARCH REF: D-44
# OWNS: Licence extraction and flagging
# DOES NOT OWN: Legal decisions (owner review)
# CONNECTS TO (external boundaries only):
#   - called by NOTICE: main
#   - called by tests/scripts/test_gen_notice.py: licence_of, flag, main, ROOT, FLAG_WEAK, FLAG_STRONG, FLAG_PROPRIETARY
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Write NOTICE.generated, never overwrite NOTICE; the owner merges by hand.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/scripts/test_gen_notice.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check scripts/gen_notice.py` and `uv run mypy scripts/gen_notice.py` are clean.

import argparse
import sys
import tomllib
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLAG_WEAK = ("MPL", "LGPL", "Mozilla", "EPL")
FLAG_STRONG = ("AGPL", "GPL")
FLAG_PROPRIETARY = ("Proprietary", "NVIDIA")


def licence_of(name: str) -> str:
    try:
        md = metadata.metadata(name)
    except metadata.PackageNotFoundError:
        return "NOT INSTALLED (run uv sync --all-extras first)"
    expr = md.get("License-Expression")
    if expr:
        return expr
    classifiers = [c.split("::")[-1].strip() for c in md.get_all("Classifier") or [] if c.startswith("License ::")]
    return "; ".join(classifiers) or (md.get("License") or "UNKNOWN").splitlines()[0][:80]


def flag(lic: str) -> str:
    if any(f in lic for f in FLAG_PROPRIETARY):
        return "REVIEW: proprietary terms"
    if "AGPL" in lic or ("GPL" in lic and "LGPL" not in lic):
        return "BLOCKED unless approved: strong copyleft"
    if any(f in lic for f in FLAG_WEAK):
        return "FLAG: weak copyleft (file-level obligations)"
    if "UNKNOWN" in lic:
        return "REVIEW: licence unknown"
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Regenerate NOTICE from uv.lock and installed metadata.")
    ap.add_argument("--out", type=Path, default=ROOT / "NOTICE.generated")
    args = ap.parse_args()
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    rows = []
    for pkg in lock.get("package", []):
        if pkg.get("source", {}).get("registry"):
            lic = licence_of(pkg["name"])
            rows.append(f"{pkg['name']}=={pkg['version']}  {lic}  {flag(lic)}".rstrip())
    args.out.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {args.out} ({len(rows)} packages); merge into NOTICE by hand")
    return 0


if __name__ == "__main__":
    sys.exit(main())
