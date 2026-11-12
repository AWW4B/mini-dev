# FILE: src/asf/cli/project_input.py
# ROLE: Builds the IF-01 SubmitRequest from text, files and repo path; stores attachments as blobs.
# ARCH REF: M1; p02 Project Input; IF-01
# OWNS: SubmitRequest assembly
# DOES NOT OWN: Request processing (M2)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/requests.py: SubmitRequest, TaskType (IF-01)
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (attachments)
#   - imports from src/asf/contracts/errors.py: ConfigError (bad attachments or repository)
#   - called by src/asf/cli/commands/run.py: build_submit_request
#   - called by tests/cli/test_project_input.py: build_submit_request, MAX_ATTACHMENT_BYTES
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
# DONE WHEN: (1) tests/cli/test_project_input.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/project_input.py` and `uv run mypy src/asf/cli/project_input.py` are clean.

from pathlib import Path

from asf.contracts.errors import ConfigError
from asf.contracts.requests import SubmitRequest, TaskType
from asf.m5_shared.workspace.blobs import BlobStore

MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024
_URL_PREFIXES = ("http://", "https://", "git@", "ssh://", "git://")


def build_submit_request(project_id: str, text: str, files: list[Path], repo: str | None, mode: TaskType | None) -> SubmitRequest:
    """Build the IF-01 SubmitRequest; attachments are stored as blobs and referenced by their sha-256 ref."""
    if not text.strip() and not files and not repo:
        raise ConfigError("Give the request as text (--input), as files (--file) or as a repository (--repo).")
    blobs = BlobStore()
    refs: list[str] = []
    for file in files:
        if not file.is_file():
            raise ConfigError(f"Attachment not found: {file}")
        if file.stat().st_size > MAX_ATTACHMENT_BYTES:
            raise ConfigError(f"Attachment {file.name} is larger than {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB.")
        refs.append(blobs.put(file.read_bytes()))
    repo_ref: str | None = None
    if repo:
        if repo.startswith(_URL_PREFIXES):
            repo_ref = repo
        elif Path(repo).is_dir():
            repo_ref = str(Path(repo).resolve())
        else:
            raise ConfigError(f"Repository not found: {repo} (not a directory and not a git URL).")
    return SubmitRequest.model_validate(
        {"project_id": project_id, "text": text.strip(), "attachment_refs": refs, "repo_ref": repo_ref, "mode_hint": mode}
    )
