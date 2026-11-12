# FILE: tests/m5_shared/context/test_repo_index.py
# ROLE: Tests that prove src/asf/m5_shared/context/repo_index.py meets its DONE WHEN conditions.
# ARCH REF: M5; p12; D-30; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/context/repo_index.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/context/repo_index.py: RepoIndex (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use the tmp_path fixture or the fake_paths fixture for every filesystem location.
#   6. Use the fakes from tests/conftest.py instead of real GPUs, networks, sandboxes or model providers unless the test is marked needs_gpu, needs_network or needs_sandbox.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; real API keys; network access in unmarked tests; sleeping for timing (use the fake clock)
# ERRORS: Failures surface as pytest assertion failures.
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/context/test_repo_index.py` on Windows and Linux once src/asf/m5_shared/context/repo_index.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/context/test_repo_index.py` and `uv run mypy tests/m5_shared/context/test_repo_index.py` are clean.

from pathlib import Path
from typing import Any

import pytest

import asf.m5_shared.context.repo_index as index_mod
from asf.m5_shared.context.repo_index import RepoIndex


def test_repo_index_meets_contract(tmp_path: Path, fake_paths: Any) -> None:
    """Prove RepoIndex behaves as declared in src/asf/m5_shared/context/repo_index.py."""
    _ = fake_paths

    src_dir = tmp_path / "src" / "math_pkg"
    src_dir.mkdir(parents=True)
    calc_file = src_dir / "calc.py"
    calc_file.write_text(
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n\n"
        "class Calculator:\n"
        "    def multiply(self, a: int, b: int) -> int:\n"
        "        return a * b\n",
        encoding="utf-8",
    )

    test_dir = tmp_path / "tests" / "math_pkg"
    test_dir.mkdir(parents=True)
    test_file = test_dir / "test_calc.py"
    test_file.write_text(
        "def test_add() -> None:\n"
        "    assert True\n",
        encoding="utf-8",
    )

    index = RepoIndex()
    index.build(tmp_path)

    # 1. Symbols for calc.py
    symbols = index.symbols_for(["src/math_pkg/calc.py"])
    assert any("add" in s for s in symbols)
    assert any("Calculator" in s for s in symbols)

    # 2. Tests for source file
    matching_tests = index.tests_for(["src/math_pkg/calc.py"])
    assert len(matching_tests) >= 1
    assert any("test_calc.py" in t for t in matching_tests)

    # 3. Source for test file
    matching_sources = index.tests_for(["tests/math_pkg/test_calc.py"])
    assert len(matching_sources) >= 1
    assert any("calc.py" in s for s in matching_sources)

    # 4. Search
    search_hits = index.search("Calculator")
    assert any("calc.py" in h for h in search_hits)

    search_fn = index.search("multiply")
    assert any("calc.py" in h for h in search_fn)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_file_text_is_not_kept_in_memory_but_is_still_searchable(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    marker = "unique_marker_phrase_for_search"
    _write(tmp_path, "docs/notes.md", f"# Notes\n{marker}\n" + "filler line\n" * 1000)
    index = RepoIndex()
    index.build(tmp_path)

    retained = [v for v in vars(index).values() if isinstance(v, (dict, list))]
    assert marker not in repr(retained)
    assert index.search(marker) == ["docs/notes.md"]


def test_vendored_and_oversized_files_are_not_indexed(tmp_path: Path, fake_paths: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _ = fake_paths
    monkeypatch.setattr(index_mod, "MAX_INDEXED_FILE_BYTES", 100)
    _write(tmp_path, "node_modules/dep/index.py", "def vendored(): pass\n")
    _write(tmp_path, ".venv/lib/mod.py", "def venv_fn(): pass\n")
    _write(tmp_path, "big.py", "def big_fn(): pass\n" + "# padding\n" * 50)
    _write(tmp_path, "ok.py", "def ok_fn(): pass\n")
    index = RepoIndex()
    index.build(tmp_path)
    assert index.symbols_for(["ok.py"]) == ["def ok_fn"]
    assert index.symbols_for(["node_modules/dep/index.py", ".venv/lib/mod.py", "big.py"]) == []
    assert index.search("") == ["ok.py"]


def test_invalid_python_still_yields_symbols_from_a_line_scan(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    _write(tmp_path, "broken.py", "def alive(:\n    pass\nclass Thing:\n")
    index = RepoIndex()
    index.build(tmp_path)
    symbols = index.symbols_for(["broken.py"])
    assert "class Thing" in symbols


def test_search_stops_reading_files_once_it_has_enough_hits(tmp_path: Path, fake_paths: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _ = fake_paths
    for i in range(30):
        _write(tmp_path, f"f{i:02d}.txt", "needle in a haystack\n")
    index = RepoIndex()
    index.build(tmp_path)
    reads: list[str] = []
    original = index._read

    def counting_read(rel: str) -> str:
        reads.append(rel)
        return original(rel)

    monkeypatch.setattr(index, "_read", counting_read)
    hits = index.search("needle", max_hits=3)
    assert len(hits) == 3
    assert len(reads) == 3


def test_test_map_handles_many_files_and_has_no_duplicates(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    for i in range(300):
        _write(tmp_path, f"src/pkg/mod{i}.py", "x = 1\n")
        _write(tmp_path, f"tests/pkg/test_mod{i}.py", "def test_x(): pass\n")
    index = RepoIndex()
    index.build(tmp_path)
    assert index.tests_for(["src/pkg/mod7.py"]) == ["tests/pkg/test_mod7.py"]
    assert index.tests_for(["tests/pkg/test_mod7.py"]) == ["src/pkg/mod7.py"]
