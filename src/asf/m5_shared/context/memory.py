# FILE: src/asf/m5_shared/context/memory.py
# ROLE: Decision log and project memory with tag lookup and invalidation by source hash.
# ARCH REF: M5; p12 memory; D-32
# OWNS: Memory rows
# DOES NOT OWN: Conversation compaction (compaction.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (persistence)
#   - called by src/asf/m5_shared/context/context_service.py: ProjectMemory
#   - called by tests/m5_shared/context/test_memory.py: ProjectMemory
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/context/test_memory.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/context/memory.py` and `uv run mypy src/asf/m5_shared/context/memory.py` are clean.

class ProjectMemory:
    def record_decision(self, text: str, tags: list[str], source_hashes: dict[str, str]) -> None:
        raise NotImplementedError

    def relevant(self, tags: list[str], limit: int = 10) -> list[str]:
        raise NotImplementedError

    def invalidate_changed(self, current_hashes: dict[str, str]) -> int:
        raise NotImplementedError
