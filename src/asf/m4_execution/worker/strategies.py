# FILE: src/asf/m4_execution/worker/strategies.py
# ROLE: Worker strategies: tool_loop, whole_file_edit, diff_edit, code_exec — all producing the same metrics.
# ARCH REF: M4; p07; D-09 worker strategies; D-19
# OWNS: Strategy step functions
# DOES NOT OWN: Gates (verification)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (IF-12 model calls)
#   - imports from src/asf/m5_shared/tools/executor.py: ToolExecutor (IF-14 tool calls)
#   - imports from src/asf/m5_shared/tools/codeexec/runner.py: execute_code (code_exec strategy)
#   - imports from src/asf/contracts/tasks.py: LeafTaskSpec (task)
#   - called by src/asf/m4_execution/worker/worker_graph.py: run_strategy
#   - called by tests/m4_execution/worker/test_strategies.py: run_strategy, WorkerStrategyName
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. code_exec is used only when the active sandbox tier is A; otherwise fall back to tool_loop and log why.
#   6. Use these Agent Skills (load via SkillsRegistry): skills/python-module-from-contract/SKILL.md.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m4_execution/worker/test_strategies.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m4_execution/worker/strategies.py` and `uv run mypy src/asf/m4_execution/worker/strategies.py` are clean.

from typing import Literal

from asf.contracts.tasks import LeafTaskSpec

WorkerStrategyName = Literal["tool_loop", "whole_file_edit", "diff_edit", "code_exec"]


def run_strategy(name: WorkerStrategyName, spec: LeafTaskSpec, worktree: str) -> str:
    """Run the bounded loop; return the worker self-report."""
    raise NotImplementedError
