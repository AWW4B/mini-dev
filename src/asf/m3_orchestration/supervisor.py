# FILE: src/asf/m3_orchestration/supervisor.py
# ROLE: Supervisor: counts what went wrong across runs (deterministic), then an analyst agent proposes system changes that are checked against those facts.
# ARCH REF: M3; p04 Escalation & Recovery (learning from past runs)
# OWNS: SUPERVISOR.md content, the per-project history of problems (supervisor_history.jsonl)
# DOES NOT OWN: Changing code or configuration (it only proposes; a person or a coding session applies the change), the delivery report (delivery.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/delivery.py: diagnose_project (the problems of this run with cause and fix)
#   - reads <project>/.factory/logs/trace.jsonl (model_call events: role, tokens)
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (the analyst agent; imported when needed)
#   - imports from src/asf/contracts/budget.py: RunBudget (budget of the analyst call)
#   - called by src/asf/m3_orchestration/autonomy.py: write_supervisor_notes
#   - called by tests/m3_orchestration/test_supervisor.py: write_supervisor_notes
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Propose, never apply: nothing outside .factory/ is written, and the file says so.
#   6. Facts are computed by code; the agent only reads them and proposes. A proposal that cites a task or cause the data does not hold is dropped and the drop is reported.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/test_supervisor.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/supervisor.py` and `uv run mypy src/asf/m3_orchestration/supervisor.py` are clean.

import json
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from asf.m3_orchestration.delivery import diagnose_project

Analyst = Callable[[str], str]

_ROLE = (
    "You are the supervisor of an automated software factory (planner, decomposer, small local coder, gate, bigger helper models). "
    "You are given FACTS computed by code from the factory's own history. Propose changes to the FACTORY ITSELF (its code, prompts, "
    "thresholds or tools) that would prevent the recorded problems. Cite only task ids and causes that appear in the FACTS. "
    'Reply with JSON only: [{"change": "<what to change in the factory>", "why": "<one sentence>", "evidence": ["<task id or cause from the FACTS>"]}]. '
    "At most five items, the most valuable first."
)


def _model_analyst(profile: str) -> Analyst:
    """The analyst agent: a bigger model with the role above as its system prompt."""
    from asf.contracts.budget import RunBudget
    from asf.m5_shared.gateway.gateway import ModelGateway

    budget = RunBudget.model_validate({"run_id": "supervisor", "max_remote_tokens": 200_000, "max_local_tokens": 0, "max_api_spend": 1.0, "max_wall_clock_s": 3600, "max_task_nodes": 1})
    gateway = ModelGateway(profile or ModelGateway.default_profile_name(), budget)

    def ask(facts: str) -> str:
        reply = gateway.model_for(cast(Any, "T3"), purpose="supervisor").invoke(f"{_ROLE}\n\nFACTS:\n{facts}")
        return str(getattr(reply, "content", reply))

    return ask


def _usage(project_root: Path) -> list[str]:
    """Model calls and tokens per role and purpose, summed from the trace: where the effort went."""
    path = project_root / ".factory" / "logs" / "trace.jsonl"
    calls: Counter[tuple[str, str]] = Counter()
    tokens: Counter[tuple[str, str]] = Counter()
    if path.is_file():
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if '"model_call"' not in raw:
                continue
            try:
                data = json.loads(raw).get("data") or {}
            except ValueError:
                continue
            key = (str(data.get("role")), str(data.get("purpose")))
            calls[key] += 1
            tokens[key] += int(data.get("tokens_in") or 0) + int(data.get("tokens_out") or 0)
    return [f"| {role} | {purpose} | {n} | {tokens[(role, purpose)]} |" for (role, purpose), n in calls.most_common()]


def _cited(evidence: str, known: set[str]) -> bool:
    """Evidence counts when it names a known task (in full or by its last part, 'core' for run_x-core) or quotes most of a known cause."""
    e = evidence.strip().lower()
    for k in (x.lower() for x in known):
        if e and (e in k or k in e or e == k.rsplit("-", 1)[-1]):
            return True
        words = set(e.split())
        if len(words) >= 4 and len(words & set(k.split())) >= 0.6 * len(words):
            return True
    return False


def _checked(raw: str, known: set[str]) -> tuple[list[dict[str, Any]], int]:
    """The agent's proposals that cite only evidence the facts contain, and how many were dropped (nothing is hidden: the count is reported)."""
    try:
        items = json.loads(raw[raw.find("[") : raw.rfind("]") + 1])
    except ValueError:
        return [], -1
    kept: list[dict[str, Any]] = []
    dropped = 0
    for item in items if isinstance(items, list) else []:
        evidence = [str(e) for e in item.get("evidence", [])] if isinstance(item, dict) else []
        if isinstance(item, dict) and item.get("change") and evidence and all(_cited(e, known) for e in evidence):
            kept.append(item)
        else:
            dropped += 1
    return kept[:5], dropped


def write_supervisor_notes(project_root: Path, analyst: Analyst | None = None, profile: str = "") -> Path:
    """Write SUPERVISOR.md: recurring problems counted by code, where the effort went, then the analyst agent's checked proposals."""
    problems = diagnose_project(project_root)  # [(task_id, state, cause, fix)]
    history = project_root / ".factory" / "supervisor_history.jsonl"
    history.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    with history.open("a", encoding="utf-8") as fh:
        for task_id, state, cause, fix in problems:
            fh.write(json.dumps({"at": stamp, "task": task_id, "state": state, "cause": cause, "fix": fix}) + "\n")
    seen: Counter[tuple[str, str]] = Counter()
    for raw in history.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        seen[(row["cause"], row["fix"])] += 1
    lines = [
        "# Supervisor notes",
        "",
        "Proposals read from the history of this project's runs. Nothing was changed: a person or a coding session applies them.",
        "",
        f"Problems recorded so far: {sum(seen.values())}; in this run: {len(problems)}.",
        "",
        "## Facts (computed by code)",
        "",
    ]
    if not seen:
        lines.append("No task has failed in the recorded history.")
    for (cause, fix), count in seen.most_common():
        lines.append(f"- Seen {count} time(s): {cause} Rule-based fix: {fix}")
    usage = _usage(project_root)
    if usage:
        lines += ["", "| role | purpose | calls | tokens |", "|---|---|---|---|", *usage]
    lines += ["", "## Analyst agent's proposals (model-written; each cites evidence that was checked against the facts)", ""]
    if not problems:
        lines.append("Nothing to analyse in this run.")
    else:
        facts = "\n".join([*(f"- task {t} ({st}): {c} Evidence fix: {f}" for t, st, c, f in problems), *usage[:10]])
        known = {t for t, _s, _c, _f in problems} | {c for _t, _s, c, _f in problems}
        try:
            ask = analyst if analyst is not None else _model_analyst(profile)
            kept, dropped = _checked(ask(facts), known)
        except Exception as err:  # noqa: BLE001 - the facts above stand without the agent, and the file says why there is none
            kept, dropped = [], -2
            lines.append(f"The analyst agent could not be reached ({type(err).__name__}: {str(err)[:120]}); only the code-computed facts above are available.")
        if dropped == -1:
            lines.append("The analyst agent answered in a form that could not be read; its answer was discarded.")
        for item in kept:
            lines.append(f"- **{item['change']}** - {item.get('why', '')} (evidence: {', '.join(str(e) for e in item['evidence'])})")
        if dropped > 0:
            lines.append(f"- {dropped} proposal(s) were dropped because they cited evidence that is not in the facts.")
    target = project_root / ".factory" / "deliver" / "SUPERVISOR.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
