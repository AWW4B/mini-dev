# FILE: src/asf/web/projection.py
# ROLE: Projects events into the viewer model: participants (role, colour, avatar, model tier, task, short result) and expandable details.
# ARCH REF: M1; p02 Active Group Chat; IF-18; D-14b
# OWNS: View-model projection and detail lookup (diff, test log, ContextPack manifest)
# DOES NOT OWN: Narrative text (narrative.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/events/event_log.py: EventLog (read-only reads)
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (details)
#   - imports from src/asf/web/narrative.py: build_narrative, NarrativeItem (narrative)
#   - called by src/asf/web/server.py: Projection
#   - called by tests/web/test_projection.py: Participant, Projection
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Open state.db read-only (SQLite URI mode=ro).
#   6. Participant colour/avatar are deterministic from the role name.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/web/test_projection.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/web/projection.py` and `uv run mypy src/asf/web/projection.py` are clean.

from typing import Any

from pydantic import BaseModel


class Participant(BaseModel):
    key: str
    role: str
    colour: str
    avatar: str
    model_tier: str | None
    current_task: str | None
    last_result: str | None


class Projection:
    def __init__(self, run_id: str) -> None:
        raise NotImplementedError

    def participants(self) -> list[Participant]:
        raise NotImplementedError

    def page(self, after_seq: int, limit: int = 200, include_internal: bool = False) -> dict[str, Any]:
        raise NotImplementedError

    def detail(self, ref: str) -> dict[str, Any]:
        raise NotImplementedError
