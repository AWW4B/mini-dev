# FILE: src/asf/m5_shared/metrics/advisories.py
# ROLE: Turns snapshots, budgets and probes into soft/hard ResourceAdvisories (IF-20).
# ARCH REF: M5; p10; IF-20 ResourceAdvisory; p06 budgets
# OWNS: Threshold rules
# DOES NOT OWN: Acting on advisories (scheduler, run_control)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/metrics.py: MetricsSnapshot, ResourceAdvisory (IF-19/IF-20)
#   - imports from src/asf/contracts/budget.py: RunBudget (limits)
#   - called by tests/m5_shared/metrics/test_advisories.py: evaluate_thresholds
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/metrics/test_advisories.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/metrics/advisories.py` and `uv run mypy src/asf/m5_shared/metrics/advisories.py` are clean.

from asf.contracts.budget import RunBudget
from asf.contracts.metrics import MetricsSnapshot, ResourceAdvisory


def evaluate_thresholds(snapshot: MetricsSnapshot, budget: RunBudget) -> list[ResourceAdvisory]:
    advisories: list[ResourceAdvisory] = []
    values = snapshot.values

    alert_frac = getattr(budget, "alert_fraction", 0.8)

    # 1. Spend check
    cost = values.get("cost", 0.0) + getattr(budget, "used_api_spend", 0.0)
    max_spend = getattr(budget, "max_api_spend", 0.0)
    if max_spend > 0:
        if cost >= max_spend:
            advisories.append(
                ResourceAdvisory(
                    kind="budget_spend",
                    severity="hard",
                    max_slots=0,
                    detail=f"API spend {cost:.2f} reached or exceeded limit {max_spend:.2f}",
                )
            )
        elif cost >= max_spend * alert_frac:
            advisories.append(
                ResourceAdvisory(
                    kind="budget_spend",
                    severity="soft",
                    detail=f"API spend {cost:.2f} reached {alert_frac * 100:.0f}% of limit {max_spend:.2f}",
                )
            )

    # 2. Remote tokens check
    in_tok = values.get("input_tokens", 0.0)
    out_tok = values.get("output_tokens", 0.0)
    tot_tokens = in_tok + out_tok + getattr(budget, "used_remote_tokens", 0)
    max_tokens = getattr(budget, "max_remote_tokens", 0)
    if max_tokens > 0:
        if tot_tokens >= max_tokens:
            advisories.append(
                ResourceAdvisory(
                    kind="budget_tokens",
                    severity="hard",
                    max_slots=0,
                    detail=f"Token usage {int(tot_tokens)} reached or exceeded limit {max_tokens}",
                )
            )
        elif tot_tokens >= max_tokens * alert_frac:
            advisories.append(
                ResourceAdvisory(
                    kind="budget_tokens",
                    severity="soft",
                    detail=f"Token usage {int(tot_tokens)} reached {alert_frac * 100:.0f}% of limit {max_tokens}",
                )
            )

    # 3. Task nodes check
    nodes = values.get("task_nodes", 0.0) + getattr(budget, "used_task_nodes", 0)
    max_nodes = getattr(budget, "max_task_nodes", 0)
    if max_nodes > 0:
        if nodes >= max_nodes:
            advisories.append(
                ResourceAdvisory(
                    kind="budget_nodes",
                    severity="hard",
                    max_slots=0,
                    detail=f"Task nodes {int(nodes)} reached or exceeded limit {max_nodes}",
                )
            )
        elif nodes >= max_nodes * alert_frac:
            advisories.append(
                ResourceAdvisory(
                    kind="budget_nodes",
                    severity="soft",
                    detail=f"Task nodes {int(nodes)} reached {alert_frac * 100:.0f}% of limit {max_nodes}",
                )
            )

    return advisories
