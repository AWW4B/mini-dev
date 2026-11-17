# FILE: src/asf/m5_shared/memory/budgets.py
# ROLE: Splits a model's context window into per-layer token budgets from the role's percentage shares.
# ARCH REF: M5; p12 Context & Memory Service; docs/architecture/MEMORY_ARCHITECTURE.md
# OWNS: LayerBudgets and the share arithmetic
# DOES NOT OWN: Building the prompt (context_service.py, router.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/memory/device_budget.py: pct (percentage parsing)
#   - imports from src/asf/contracts/errors.py: ConfigError (invalid shares)
#   - called by tests/m5_shared/memory/test_budgets.py: budgets_for, layer_shares, LAYERS
#   - called by src/asf/m5_shared/memory/router.py: LayerBudgets
#   - called by tests/m5_shared/memory/test_router.py: budgets_for
#   - called by src/asf/m5_shared/memory/hooks.py: budgets_for
#   - called by src/asf/cli/commands/memory_cmd.py: LAYERS, budgets_for
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/memory/test_budgets.py pass on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/memory/budgets.py` and `uv run mypy src/asf/m5_shared/memory/budgets.py` are clean.

from typing import Any

from pydantic import BaseModel

from asf.contracts.errors import ConfigError
from asf.m5_shared.memory.device_budget import pct

LAYERS = ("output", "system", "procedural", "task", "working", "tools", "episodic", "semantic", "session")


class LayerBudgets(BaseModel):
    """Token budgets of one model call, each a percentage share of that model's usable window."""

    role: str
    window_tokens: int
    output: int
    system: int
    procedural: int
    task: int
    working: int
    tools: int
    episodic: int
    semantic: int
    session: int

    @property
    def input_tokens(self) -> int:
        """Everything the prompt may hold: the window minus the reserved answer."""
        return self.window_tokens - self.output

    @property
    def memory_tokens(self) -> int:
        """The share retrieved memory may take (episodic + semantic + session)."""
        return self.episodic + self.semantic + self.session

    def get(self, layer: str) -> int:
        if layer not in LAYERS:
            raise ConfigError(f"unknown memory layer '{layer}'; use one of {', '.join(LAYERS)}")
        return int(getattr(self, layer))


def layer_shares(config: dict[str, Any], role: str) -> dict[str, float]:
    """The fractions of [layers.<role>]; they must cover every layer and sum to 100%."""
    table = config.get("layers", {}).get(role)
    if not isinstance(table, dict):
        raise ConfigError(f"memory.toml has no [layers.{role}] table; add one whose shares sum to 100.")
    shares = {layer: pct(table, layer) for layer in LAYERS}
    total = round(sum(shares.values()) * 100, 6)
    if total != 100:
        raise ConfigError(f"[layers.{role}] in memory.toml sums to {total}%, not 100%.")
    return shares


def budgets_for(role: str, window_tokens: int, config: dict[str, Any]) -> LayerBudgets:
    """Split ``window_tokens`` across the layers by the role's percentages (floored; the remainder goes to output)."""
    if window_tokens <= 0:
        raise ConfigError(f"the context window of role {role} must be positive, got {window_tokens}")
    shares = layer_shares(config, role)
    values = {layer: int(window_tokens * share) for layer, share in shares.items()}
    values["output"] += window_tokens - sum(values.values())
    return LayerBudgets(role=role, window_tokens=window_tokens, **values)
