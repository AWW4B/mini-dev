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
import logging
import os
from pathlib import Path

from asf.platform.select import get_platform  # noqa: F401

logger = logging.getLogger(__name__)

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
_TEXT_SUFFIXES = frozenset({".py", ".md", ".toml", ".json", ".txt"})
MAX_INDEXED_FILE_BYTES = 1_000_000  # larger text files are listed but neither parsed nor searched


def _extract_py_symbols(text: str) -> list[str]:
    symbols: list[str] = []
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        # Not valid Python (or too deeply nested): fall back to a line scan so partial files are still indexed.
        for line in text.splitlines():
            s = line.strip()
            if s.startswith(("def ", "class ", "async def ")):
                symbols.append(s.split(":")[0])
        return symbols
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            symbols.append(f"def {node.name}")
        elif isinstance(node, ast.AsyncFunctionDef):
            symbols.append(f"async def {node.name}")
        elif isinstance(node, ast.ClassDef):
            symbols.append(f"class {node.name}")
    return symbols


def _link(mapping: dict[str, list[str]], key: str, value: str) -> None:
    bucket = mapping.setdefault(key, [])
    if value not in bucket:
        bucket.append(value)


class RepoIndex:
    """Static index of a repository. Only paths and symbols stay in memory; file text is read on demand."""

    _root: Path | None
    _file_symbols: dict[str, list[str]]
    _text_files: list[str]
    _source_to_test: dict[str, list[str]]
    _test_to_source: dict[str, list[str]]

    def __init__(self, root: Path | None = None) -> None:
        self._root = root
        self._file_symbols = {}
        self._text_files = []
        self._source_to_test = {}
        self._test_to_source = {}
        if root is not None:
            self.build(root)

    def build(self, root: Path) -> None:
        self._root = root
        self._file_symbols.clear()
        self._text_files.clear()
        self._source_to_test.clear()
        self._test_to_source.clear()

        all_rel_paths: list[str] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
            base = Path(dirpath)
            for name in sorted(filenames):
                path = base / name
                rel_str = path.relative_to(root).as_posix()
                all_rel_paths.append(rel_str)
                if path.suffix not in _TEXT_SUFFIXES:
                    continue
                try:
                    if path.stat().st_size > MAX_INDEXED_FILE_BYTES:
                        continue
                    content = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    logger.debug("skipping unreadable file %s", rel_str, exc_info=True)
                    continue
                self._text_files.append(rel_str)
                if path.suffix == ".py":
                    self._file_symbols[rel_str] = _extract_py_symbols(content)

        self._build_test_map(all_rel_paths)

    def _build_test_map(self, all_rel_paths: list[str]) -> None:
        """Link tests and sources through name lookups (linear in the number of files, not quadratic)."""
        by_name: dict[str, list[str]] = {}
        by_stem: dict[str, list[str]] = {}
        for rel in all_rel_paths:
            p = Path(rel)
            by_name.setdefault(p.name, []).append(rel)
            by_stem.setdefault(p.stem, []).append(rel)

        for path_str in all_rel_paths:
            p = Path(path_str)
            if p.name.startswith("test_") or "tests/" in path_str:
                # e.g. tests/math_pkg/test_calc.py -> math_pkg/calc.py or src/math_pkg/calc.py
                stem = p.name[len("test_"):] if p.name.startswith("test_") else p.name
                candidates = [*by_name.get(stem, []), *by_stem.get(Path(stem).stem, [])]
                for other in dict.fromkeys(candidates):
                    if other != path_str:
                        _link(self._test_to_source, path_str, other)
                        _link(self._source_to_test, other, path_str)
            else:
                for other in by_name.get(f"test_{p.name}", []):
                    _link(self._source_to_test, path_str, other)
                    _link(self._test_to_source, other, path_str)

    def _read(self, rel_path: str) -> str:
        if self._root is None:
            return ""
        try:
            return (self._root / rel_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.debug("could not read %s for the search", rel_path, exc_info=True)
            return ""

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
                wanted = stem[len("test_"):] if stem.startswith("test_") else f"test_{stem}"
                results.extend(s for s in self._text_files if Path(s).stem == wanted)
        return list(dict.fromkeys(results))

    def search(self, text: str, max_hits: int = 20) -> list[str]:
        q = text.lower().strip()
        if not q:
            return self._text_files[:max_hits]

        hits: list[str] = []
        seen: set[str] = set()

        def add(rel_path: str) -> bool:
            if rel_path not in seen:
                seen.add(rel_path)
                hits.append(rel_path)
            return len(hits) >= max_hits

        # 1. Path matches
        for rel_path in self._text_files:
            if q in rel_path.lower() and add(rel_path):
                return hits

        # 2. Symbol matches
        for rel_path, syms in self._file_symbols.items():
            if any(q in s.lower() for s in syms) and add(rel_path):
                return hits

        # 3. Content matches: files are read one at a time, and the scan stops as soon as there are enough hits
        for rel_path in self._text_files:
            if rel_path not in seen and q in self._read(rel_path).lower() and add(rel_path):
                return hits

        return hits
