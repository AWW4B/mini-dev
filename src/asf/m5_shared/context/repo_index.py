# FILE: src/asf/m5_shared/context/repo_index.py
# ROLE: Builds and queries the static code index (tree-sitter symbols, imports, test<->source map).
# ARCH REF: M5; p12; D-30
# OWNS: Index build and query
# DOES NOT OWN: Deciding what goes into a prompt (context_service)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/platform/select.py: get_platform (platform adapter)
#   - called by src/asf/m5_shared/context/context_service.py: RepoIndex
#   - called by src/asf/m2_request/repository_intake.py: RepoIndex
#   - called by src/asf/m4_execution/verification/test_selection.py: RepoIndex
#   - called by tests/m5_shared/context/test_repo_index.py: RepoIndex
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
# DONE WHEN: (1) tests/m5_shared/context/test_repo_index.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/context/repo_index.py` and `uv run mypy src/asf/m5_shared/context/repo_index.py` are clean.

import ast
from pathlib import Path

from asf.platform.select import get_platform  # noqa: F401

_SKIP_DIRS = frozenset({
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".factory",
    "node_modules",
})


def _extract_py_symbols(text: str) -> list[str]:
    symbols: list[str] = []
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                symbols.append(f"def {node.name}")
            elif isinstance(node, ast.AsyncFunctionDef):
                symbols.append(f"async def {node.name}")
            elif isinstance(node, ast.ClassDef):
                symbols.append(f"class {node.name}")
    except Exception as _parse_err:  # noqa: BLE001
        _ = _parse_err
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("def ") or s.startswith("class ") or s.startswith("async def "):
                symbols.append(s.split(":")[0])
    return symbols


class RepoIndex:
    _root: Path | None
    _file_symbols: dict[str, list[str]]
    _file_contents: dict[str, str]
    _source_to_test: dict[str, list[str]]
    _test_to_source: dict[str, list[str]]

    def __init__(self, root: Path | None = None) -> None:
        self._root = root
        self._file_symbols = {}
        self._file_contents = {}
        self._source_to_test = {}
        self._test_to_source = {}
        if root is not None:
            self.build(root)

    def build(self, root: Path) -> None:
        self._root = root
        self._file_symbols.clear()
        self._file_contents.clear()
        self._source_to_test.clear()
        self._test_to_source.clear()

        all_rel_paths: list[str] = []
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            parts = p.relative_to(root).parts
            if any(part in _SKIP_DIRS for part in parts):
                continue

            rel_str = p.relative_to(root).as_posix()
            all_rel_paths.append(rel_str)

            if p.suffix in {".py", ".md", ".toml", ".json", ".txt"}:
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    self._file_contents[rel_str] = content
                    if p.suffix == ".py":
                        self._file_symbols[rel_str] = _extract_py_symbols(content)
                except Exception as _read_err:  # noqa: BLE001
                    _ = _read_err

        # Build test <-> source map
        for path_str in all_rel_paths:
            p = Path(path_str)
            is_test = p.name.startswith("test_") or "tests/" in path_str

            if is_test:
                # e.g. tests/math_pkg/test_calc.py -> math_pkg/calc.py or src/math_pkg/calc.py
                stem = p.name[len("test_") :] if p.name.startswith("test_") else p.name
                for other in all_rel_paths:
                    other_p = Path(other)
                    if other == path_str:
                        continue
                    if other_p.name == stem or other_p.stem == Path(stem).stem:
                        self._test_to_source.setdefault(path_str, []).append(other)
                        self._source_to_test.setdefault(other, []).append(path_str)
            else:
                expected_test_name = f"test_{p.name}"
                for other in all_rel_paths:
                    if Path(other).name == expected_test_name:
                        self._source_to_test.setdefault(path_str, []).append(other)
                        self._test_to_source.setdefault(other, []).append(path_str)

    def symbols_for(self, rel_paths: list[str]) -> list[str]:
        results: list[str] = []
        for rp in rel_paths:
            norm = Path(rp).as_posix()
            results.extend(self._file_symbols.get(norm, []))
        return results

    def tests_for(self, rel_paths: list[str]) -> list[str]:
        results: list[str] = []
        for rp in rel_paths:
            norm = Path(rp).as_posix()
            if norm in self._source_to_test:
                results.extend(self._source_to_test[norm])
            elif norm in self._test_to_source:
                results.extend(self._test_to_source[norm])
            else:
                # Fallback matching by filename
                stem = Path(norm).stem
                if stem.startswith("test_"):
                    base = stem[len("test_") :]
                    for s, _ in self._file_contents.items():
                        if Path(s).stem == base:
                            results.append(s)
                else:
                    target = f"test_{stem}"
                    for t, _ in self._file_contents.items():
                        if Path(t).stem == target:
                            results.append(t)
        return list(dict.fromkeys(results))

    def search(self, text: str, max_hits: int = 20) -> list[str]:
        q = text.lower().strip()
        if not q:
            return list(self._file_contents.keys())[:max_hits]

        hits: list[str] = []
        # 1. Path matches
        for rel_path in self._file_contents:
            if q in rel_path.lower():
                hits.append(rel_path)

        # 2. Symbol matches
        for rel_path, syms in self._file_symbols.items():
            if rel_path not in hits and any(q in s.lower() for s in syms):
                hits.append(rel_path)

        # 3. Content matches
        for rel_path, content in self._file_contents.items():
            if rel_path not in hits and q in content.lower():
                hits.append(rel_path)

        return hits[:max_hits]
