# FILE: src/asf/m5_shared/context/context_service.py
# ROLE: Builds every ContextPack under a token budget, returning CONTEXT_OVERFLOW instead of truncating must-haves.
# ARCH REF: M5; p12 Context & Memory Service; IF-11 ContextRequest/ContextPack; IF-08 (capsules); A-1; D-31
# OWNS: Context assembly and manifest persistence
# DOES NOT OWN: Model calls for the task itself
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/context.py: ContextPack, ContextRequest (IF-11)
#   - imports from src/asf/m5_shared/registry/registry.py: ContractRegistry (IF-08 capsules)
#   - imports from src/asf/m5_shared/context/repo_index.py: RepoIndex (snippets)
#   - imports from src/asf/m5_shared/context/memory.py: ProjectMemory (decisions)
#   - imports from src/asf/m5_shared/gateway/tokenizers.py: count_tokens (D-31)
#   - imports from src/asf/contracts/errors.py: ContextOverflow (error types)
#   - called by src/asf/m2_request/request_understanding.py: ContextService
#   - called by src/asf/m3_orchestration/planning/planner_graph.py: ContextService
#   - called by src/asf/m3_orchestration/decomposition/splitter.py: ContextService
#   - called by src/asf/m4_execution/worker/worker_graph.py: ContextService
#   - called by tests/m5_shared/context/test_context_service.py: ContextService
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Tier order P0..P5; P0+P1+P2 are must-haves; raise ContextOverflow with item sizes when they do not fit.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/context/test_context_service.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/context/context_service.py` and `uv run mypy src/asf/m5_shared/context/context_service.py` are clean.

from asf.contracts.context import ContextPack, ContextRequest


class ContextService:
    def build(self, request: ContextRequest) -> ContextPack:
        raise NotImplementedError

    def dry_run_fits(self, request: ContextRequest) -> bool:
        raise NotImplementedError
