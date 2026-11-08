# FILE: scripts/check_headers.py
# ROLE: Verifies every file header: required fields, FILE path, mandatory instruction, referenced paths exist, both sides of each connection agree, imported symbols exist, and (with --coverage) drawio IDs are covered.
# ARCH REF: Phase 2 validation; D-39; p15
# OWNS: Header validation rules
# DOES NOT OWN: Fixing headers (report only)
# CONNECTS TO (external boundaries only):
#   - called by .github/workflows/ci.yml: main
#   - called by tests/scripts/test_check_headers.py: repo_files, extract_header, header_owner, top_level_names, asf_imports, main, ROOT, REQUIRED, MANDATORY, SKIP_DIRS, PATH_RE, IMPORT_RE, CALLED_RE, PLACEHOLDERS
#   - called by AGENTS.md: agents run it after every change
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Use only the standard library so it runs before `uv sync`.
#   9. Exit 0 when clean, 1 when any problem is found; print one line per problem.
#   10. --coverage reads module and IF IDs from docs/architecture/AI_Software_Factory_Architecture.drawio.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) `uv run python scripts/check_headers.py --coverage` exits 0 on the generated skeleton. (2) tests/scripts/test_check_headers.py passes on Windows and Linux. (3) `uv run python scripts/check_headers.py` reports no problem for this file. (4) `uv run ruff check scripts/check_headers.py` and `uv run mypy scripts/check_headers.py` are clean.

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = ["FILE", "ROLE", "ARCH REF", "OWNS", "DOES NOT OWN", "CONNECTS TO", "INSTRUCTIONS", "FORBIDDEN", "ERRORS", "DONE WHEN"]
MANDATORY = "Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file."
SKIP_DIRS = {".git", ".venv", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", "dist", "build"}
PATH_RE = re.compile(r"(?<![\w/.-])((?:src|tests|scripts|skills|docs|\.github)/[A-Za-z0-9_./-]+|pyproject\.toml|README\.md|AGENTS\.md|LICENSE|NOTICE|uv\.lock|requirements\.lock\.txt)")
IMPORT_RE = re.compile(r"^\s*- imports from (\S+): (.+?) \(")
CALLED_RE = re.compile(r"^\s*- called by (\S+?):")
PLACEHOLDERS = ("[YOUR NAME]", "[YOUR EMAIL]")


def repo_files() -> list[Path]:
    out = []
    for p in sorted(ROOT.rglob("*")):
        if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS) and p.suffix not in {".pyc", ".gguf", ".zip"}:
            out.append(p)
    return out


def extract_header(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    name, suffix = path.name, path.suffix
    if name == "SKILL.md" and text.startswith("---"):
        text = text[text.index("\n---", 3) + 4:].lstrip("\n")
    if suffix in {".md", ".html"}:
        m = re.match(r"\s*<!--\n(.*?)\n-->", text, re.S)
        return m.group(1) if m else None
    if suffix in {".js", ".css"}:
        m = re.match(r"\s*/\*\n(.*?)\n\*/", text, re.S)
        return m.group(1) if m else None
    lines = []
    for line in text.splitlines():
        if line.startswith("#"):
            lines.append(line[2:] if line.startswith("# ") else line[1:])
        else:
            break
    return "\n".join(lines) if lines else None


def header_owner(path: Path) -> Path:
    """For a sibling header (x.header.md) return the described file x."""
    return path.with_name(path.name[: -len(".header.md")]) if path.name.endswith(".header.md") else path


def top_level_names(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def asf_imports(path: Path) -> set[str]:
    """Repo-relative files imported via `from asf... import` / `import asf...`."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "asf":
            mods.append(node.module)
        elif isinstance(node, ast.Import):
            mods.extend(a.name for a in node.names if a.name.split(".")[0] == "asf")
        for mod in mods:
            base = ROOT / "src" / Path(*mod.split("."))
            for cand in (base.with_suffix(".py"), base / "__init__.py"):
                if cand.exists():
                    found.add(cand.relative_to(ROOT).as_posix())
                    break
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify per-file plan headers.")
    ap.add_argument("--coverage", action="store_true", help="also check drawio module and IF IDs appear in headers")
    args = ap.parse_args()
    problems: list[str] = []
    headers: dict[str, str] = {}
    sibling_targets: set[str] = set()
    files = repo_files()
    for p in files:
        if p.name.endswith(".header.md"):
            sibling_targets.add(header_owner(p).relative_to(ROOT).as_posix())
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        if rel in sibling_targets:
            continue
        hdr = extract_header(p)
        if hdr is None:
            problems.append(f"{rel}: no header found (add one or a sibling {p.name}.header.md)")
            continue
        headers[rel] = hdr
    for rel, hdr in headers.items():
        for field in REQUIRED:
            if not re.search(rf"^{re.escape(field)}( \(.*?\))?:", hdr, re.M):
                problems.append(f"{rel}: missing field {field}")
        m = re.search(r"^FILE: (.+)$", hdr, re.M)
        if m and m.group(1).strip() != rel:
            problems.append(f"{rel}: FILE says {m.group(1).strip()}")
        if MANDATORY not in " ".join(hdr.split()):
            problems.append(f"{rel}: mandatory 'Implement only this file' instruction missing")
        for ref in set(PATH_RE.findall(hdr)):
            ref = ref.rstrip(".,;:)")
            if not (ROOT / ref).exists():
                problems.append(f"{rel}: referenced path does not exist: {ref}")
    for rel, hdr in headers.items():
        declared = {}
        for line in hdr.splitlines():
            m = IMPORT_RE.match(line)
            if m:
                tgt, syms = m.group(1), [s.strip() for s in m.group(2).split(",")]
                declared[tgt] = syms
                if tgt not in headers:
                    if not (ROOT / tgt).exists():
                        problems.append(f"{rel}: imports from missing file {tgt}")
                    continue
                if not any((cm := CALLED_RE.match(ln)) is not None and cm.group(1) == rel for ln in headers[tgt].splitlines()):
                    problems.append(f"{rel} -> {tgt}: target header has no matching 'called by {rel}'")
                if tgt.endswith(".py"):
                    have = top_level_names(ROOT / tgt)
                    for s in syms:
                        if s and s not in have:
                            problems.append(f"{rel} -> {tgt}: symbol {s} not defined at top level")
            m = CALLED_RE.match(line)
            if m:
                caller = m.group(1)
                if not (ROOT / caller).exists():
                    problems.append(f"{rel}: called by missing file {caller}")
                else:
                    sib = ROOT / (caller + ".header.md")
                    text = (ROOT / caller).read_text(encoding="utf-8", errors="replace")
                    if sib.exists():
                        text += sib.read_text(encoding="utf-8")
                    owner = header_owner(ROOT / rel).relative_to(ROOT).as_posix()
                    if rel not in text and owner not in text:
                        problems.append(f"{rel}: 'called by {caller}' but {caller} does not reference {owner}")
        if rel.endswith(".py"):
            for imp in asf_imports(ROOT / rel):
                if imp != rel and imp not in declared:
                    problems.append(f"{rel}: imports {imp} but CONNECTS TO does not list it")
    if args.coverage:
        drawio = next(iter(sorted((ROOT / "docs").rglob("*.drawio"))), None)
        if drawio is None:
            problems.append("coverage: no .drawio file under docs/")
        else:
            src = drawio.read_text(encoding="utf-8")
            ids = sorted(set(re.findall(r"\bIF-\d{2}[a-z]?\b", src)) | set(re.findall(r"\bM[1-5]\b", src)))
            alltext = "\n".join(headers.values())
            missing = [i for i in ids if not re.search(rf"\b{re.escape(i)}\b", alltext)]
            print(f"coverage: {len(ids) - len(missing)}/{len(ids)} drawio IDs appear in headers")
            problems += [f"coverage: {i} not referenced by any header" for i in missing]
    lic = ROOT / "LICENSE"
    if lic.exists():
        left = [ph for ph in PLACEHOLDERS if ph in lic.read_text(encoding="utf-8")]
        if left:
            print(f"REMINDER: LICENSE still contains placeholders {', '.join(left)}; fill them in before publishing.")
    for p in problems:
        print(f"PROBLEM: {p}")
    print(f"checked {len(headers)} headers: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
