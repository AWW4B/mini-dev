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

import hashlib
import uuid

from asf.contracts.context import ContextItem, ContextPack, ContextRequest, ContextTier
from asf.contracts.errors import ContextOverflow
from asf.m5_shared.context.memory import ProjectMemory
from asf.m5_shared.context.repo_index import RepoIndex
from asf.m5_shared.gateway.tokenizers import count_tokens
from asf.m5_shared.registry.registry import ContractRegistry

_MUST_HAVE_TIERS = frozenset({
    ContextTier.P0_SPEC,
    ContextTier.P1_CAPSULES,
    ContextTier.P2_ALLOWED_FILES,
})


class ContextService:
    contract_registry: ContractRegistry | None
    repo_index: RepoIndex | None
    memory: ProjectMemory | None
    _candidates: list[ContextItem]

    def __init__(
        self,
        contract_registry: ContractRegistry | None = None,
        repo_index: RepoIndex | None = None,
        memory: ProjectMemory | None = None,
    ) -> None:
        self.contract_registry = contract_registry
        self.repo_index = repo_index
        self.memory = memory
        self._candidates = []

    def add_item(self, item: ContextItem) -> None:
        self._candidates.append(item)

    def _prepare_item(self, item: ContextItem, model_id: str) -> ContextItem:
        tokens = item.tokens
        if tokens <= 0:
            tokens, _ = count_tokens(model_id, item.text)
        sha = item.sha256
        if not sha:
            sha = hashlib.sha256(item.text.encode("utf-8")).hexdigest()
        return ContextItem(
            tier=item.tier,
            source_ref=item.source_ref,
            sha256=sha,
            tokens=tokens,
            text=item.text,
        )

    def _gather_must_haves_and_optionals(self, model_id: str) -> tuple[list[ContextItem], list[ContextItem]]:
        must_haves: list[ContextItem] = []
        optionals: list[ContextItem] = []

        # Sort all candidates by tier priority (0..5)
        sorted_candidates = sorted(self._candidates, key=lambda it: int(it.tier))
        for c in sorted_candidates:
            prepared = self._prepare_item(c, model_id)
            if prepared.tier in _MUST_HAVE_TIERS:
                must_haves.append(prepared)
            else:
                optionals.append(prepared)

        return must_haves, optionals

    def dry_run_fits(self, request: ContextRequest) -> bool:
        must_haves, _ = self._gather_must_haves_and_optionals(request.model_id)
        must_have_tokens = sum(it.tokens for it in must_haves)
        return must_have_tokens <= request.budget_tokens

    def build(self, request: ContextRequest) -> ContextPack:
        must_haves, optionals = self._gather_must_haves_and_optionals(request.model_id)
        must_have_tokens = sum(it.tokens for it in must_haves)

        if must_have_tokens > request.budget_tokens:
            item_sizes = ", ".join(f"{it.source_ref}: {it.tokens} tokens" for it in must_haves)
            raise ContextOverflow(
                f"Must-have context (P0+P1+P2) requires {must_have_tokens} tokens, exceeding budget of {request.budget_tokens}. Items: [{item_sizes}]"
            )

        included: list[ContextItem] = list(must_haves)
        total_tokens = must_have_tokens

        # Fill remaining budget with optional tiers (P3, P4, P5)
        for opt in optionals:
            if total_tokens + opt.tokens <= request.budget_tokens:
                included.append(opt)
                total_tokens += opt.tokens

        return ContextPack(
            pack_id=str(uuid.uuid4()),
            task_id=request.task_id,
            role=request.role,
            budget_tokens=request.budget_tokens,
            token_count=total_tokens,
            items=included,
        )
