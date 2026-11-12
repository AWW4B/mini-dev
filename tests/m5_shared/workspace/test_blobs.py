# FILE: tests/m5_shared/workspace/test_blobs.py
# ROLE: Tests that prove src/asf/m5_shared/workspace/blobs.py meets its DONE WHEN conditions.
# ARCH REF: M5; p09 blobs; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/workspace/blobs.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobNotFound, BlobStore (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/workspace/test_blobs.py` on Windows and Linux once src/asf/m5_shared/workspace/blobs.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/workspace/test_blobs.py` and `uv run mypy tests/m5_shared/workspace/test_blobs.py` are clean.

import hashlib
from pathlib import Path

import pytest

from asf.m5_shared.workspace.blobs import BlobNotFound, BlobStore


def test_blob_store_meets_contract(tmp_path: Path) -> None:
    """Prove BlobStore behaves as declared in src/asf/m5_shared/workspace/blobs.py."""
    store = BlobStore(tmp_path)

    sample = b"hello world from blobs test"
    expected_hash = hashlib.sha256(sample).hexdigest()
    expected_ref = f"sha256:{expected_hash}"

    # put
    ref = store.put(sample)
    assert ref == expected_ref

    # get
    retrieved = store.get(ref)
    assert retrieved == sample

    # idempotent put
    ref2 = store.put(sample)
    assert ref2 == ref

    # empty payload
    empty_ref = store.put(b"")
    assert empty_ref == f"sha256:{hashlib.sha256(b'').hexdigest()}"
    assert store.get(empty_ref) == b""

    # large payload (64 KB)
    large_payload = b"A" * 65536
    large_ref = store.put(large_payload)
    assert store.get(large_ref) == large_payload

    # missing blob raises FileNotFoundError
    missing_ref = f"sha256:{'0' * 64}"
    with pytest.raises(FileNotFoundError):
        store.get(missing_ref)


def test_missing_blob_error_is_both_an_asf_error_and_a_file_not_found(tmp_path: Path) -> None:
    store = BlobStore(tmp_path)
    with pytest.raises(BlobNotFound) as info:
        store.get(f"sha256:{'1' * 64}")
    assert any(base.__name__ == "AsfError" for base in type(info.value).__mro__)
    assert isinstance(info.value, FileNotFoundError)


@pytest.mark.parametrize("ref", ["sha256:../../secret", "sha256:" + "z" * 64, "sha256:abc", "../etc/passwd", "", "sha256:" + "A" * 64])
def test_malformed_or_path_traversing_refs_are_rejected_before_touching_the_disk(tmp_path: Path, ref: str) -> None:
    outside = tmp_path / "secret"
    outside.write_bytes(b"do not read")
    store = BlobStore(tmp_path / "blobs")
    with pytest.raises(BlobNotFound):
        store.get(ref)


def test_put_leaves_no_temporary_files_behind(tmp_path: Path) -> None:
    store = BlobStore(tmp_path)
    store.put(b"payload")
    store.put(b"payload")
    leftovers = [p for p in tmp_path.rglob("*") if p.is_file() and p.name.startswith(".tmp-")]
    assert leftovers == []


def test_concurrent_writers_of_the_same_blob_all_succeed(tmp_path: Path) -> None:
    import threading

    store = BlobStore(tmp_path)
    data = b"x" * 200_000
    refs: list[str] = []
    errors: list[BaseException] = []

    def writer() -> None:
        try:
            refs.append(store.put(data))
        except BaseException as err:  # noqa: BLE001 - the test records any failure
            errors.append(err)

    threads = [threading.Thread(target=writer) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(set(refs)) == 1
    assert store.get(refs[0]) == data
