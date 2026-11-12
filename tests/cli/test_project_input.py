# FILE: tests/cli/test_project_input.py
# ROLE: Tests that prove src/asf/cli/project_input.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02 Project Input; IF-01; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/project_input.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/project_input.py: build_submit_request, MAX_ATTACHMENT_BYTES (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
#   - imports from src/asf/contracts/requests.py: TaskType (mode hints)
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (reads the stored attachment back)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/test_project_input.py` on Windows and Linux once src/asf/cli/project_input.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/test_project_input.py` and `uv run mypy tests/cli/test_project_input.py` are clean.

from pathlib import Path
from typing import Any

import pytest

import asf.cli.project_input as pi
from asf.cli.project_input import build_submit_request
from asf.contracts.requests import TaskType


def test_text_only_request(fake_paths: Any) -> None:
    _ = fake_paths
    req = build_submit_request("p1", "  Build a todo app  ", [], None, None)
    assert req.project_id == "p1" and req.text == "Build a todo app"
    assert req.attachment_refs == [] and req.repo_ref is None and req.mode_hint is None


def test_attachments_are_stored_as_blobs_and_referenced_by_sha256(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    spec = tmp_path / "spec.md"
    spec.write_bytes(b"# Requirements
")
    req = build_submit_request("p1", "see attached", [spec], None, None)
    (ref,) = req.attachment_refs
    assert ref.startswith("sha256:")
    from asf.m5_shared.workspace.blobs import BlobStore

    assert BlobStore().get(ref) == b"# Requirements\n"


def test_the_same_attachment_twice_gives_the_same_ref(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    spec = tmp_path / "spec.md"
    spec.write_text("same", encoding="utf-8")
    a = build_submit_request("p", "x", [spec], None, None)
    b = build_submit_request("p", "x", [spec], None, None)
    assert a.attachment_refs == b.attachment_refs


def test_a_local_repository_becomes_an_absolute_path_and_a_url_is_kept(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    repo = tmp_path / "repo"
    repo.mkdir()
    assert build_submit_request("p", "x", [], str(repo), None).repo_ref == str(repo.resolve())
    assert build_submit_request("p", "x", [], "https://example.com/a/b.git", None).repo_ref == "https://example.com/a/b.git"


def test_the_mode_hint_is_passed_through(fake_paths: Any) -> None:
    _ = fake_paths
    assert build_submit_request("p", "x", [], None, TaskType.DEBUG).mode_hint is TaskType.DEBUG


@pytest.mark.parametrize("bad", ["empty", "missing_file", "missing_repo"])
def test_bad_input_is_a_config_error(tmp_path: Path, fake_paths: Any, bad: str) -> None:
    _ = fake_paths
    with pytest.raises(Exception) as info:  # noqa: PT011 - ConfigError lives in contracts, which this test does not import
        if bad == "empty":
            build_submit_request("p", "   ", [], None, None)
        elif bad == "missing_file":
            build_submit_request("p", "x", [tmp_path / "nope.pdf"], None, None)
        else:
            build_submit_request("p", "x", [], str(tmp_path / "no-such-dir"), None)
    assert type(info.value).__name__ == "ConfigError"


def test_oversized_attachments_are_refused(tmp_path: Path, fake_paths: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    _ = fake_paths
    monkeypatch.setattr(pi, "MAX_ATTACHMENT_BYTES", 10)
    big = tmp_path / "big.bin"
    big.write_bytes(b"x" * 11)
    with pytest.raises(Exception) as info:  # noqa: PT011
        build_submit_request("p", "x", [big], None, None)
    assert "larger than" in str(info.value)
