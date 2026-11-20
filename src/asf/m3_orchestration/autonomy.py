# FILE: src/asf/m3_orchestration/autonomy.py
# ROLE: Autonomous driver: runs a project to its end without a person, answering every decision openly, then delivers the product and the full account.
# ARCH REF: M3; p04 Escalation & Recovery; D-13 (a run that cannot finish still ends with an honest hand-over)
# OWNS: The decision loop of an unattended run, the decision record (decisions.jsonl)
# DOES NOT OWN: Starting or executing tasks (the factory CLI does), the report text (delivery.py), the improvement notes (supervisor.py)
# CONNECTS TO (external boundaries only):
#   - runs `python -m asf` (run start, run resume, inbox answer) with argument lists in the project folder
#   - reads <project>/.factory/state.db (runs, decisions tables) read-only
#   - imports from src/asf/m3_orchestration/delivery.py: write_delivery (the report and the archive)
#   - imports from src/asf/m3_orchestration/supervisor.py: write_supervisor_notes (what the history says about the system)
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (the bigger model that reads a decision; imported when needed)
#   - imports from src/asf/contracts/budget.py: RunBudget (budget of the decision calls)
#   - called by src/asf/cli/commands/report.py: drive
#   - called by tests/m3_orchestration/test_autonomy.py: drive, choose_by_policy
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Every decision is recorded with who took it (the model or the fixed policy) and why; nothing is answered silently.
#   6. Replan a failing task once; after that abandon it and say so. Never abort the run on its own.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/test_autonomy.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/autonomy.py` and `uv run mypy src/asf/m3_orchestration/autonomy.py` are clean.

import json
import sqlite3
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from asf.m3_orchestration.delivery import write_delivery
from asf.m3_orchestration.supervisor import write_supervisor_notes

_FINISHED = ("DONE", "FAILED", "CANCELLED")
MAX_REPLANS_PER_TASK = 1

Decider = Callable[[str, str, list[str], str], tuple[str, str] | None]


def choose_by_policy(options: list[str], replans_used: int) -> tuple[str, str]:
    """The fixed fallback policy: (choice, reason). Approve, accept a larger leaf, treat as clarified, replan once, then abandon."""
    for wanted, why in (("approve", "the plan is the planner's own and was checked"), ("accept_larger_leaf", "a split was not found; try the task as it is"), ("clarified", "carry on with the stated assumptions")):
        if wanted in options:
            return wanted, f"policy: {why}"
    if "replan" in options and replans_used < MAX_REPLANS_PER_TASK:
        return "replan", "policy: one replan per task"
    if "abandon_subtree" in options:
        return "abandon_subtree", "policy: the replan budget of this task is used; it is abandoned and reported"
    return (options[0] if options else ""), "policy: no rule matched, the first option was taken"


def _record(project_root: Path, entry: dict[str, Any]) -> None:
    out = project_root / ".factory" / "deliver"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "decisions.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": datetime.now(UTC).isoformat(timespec="seconds"), **entry}) + "\n")


def _model_decider(profile: str) -> Decider:
    """The bigger model reads the decision (question, options, what the trace says) and picks one option with a reason."""
    from asf.contracts.budget import RunBudget
    from asf.m5_shared.gateway.gateway import ModelGateway

    budget = RunBudget.model_validate({"run_id": "autonomy", "max_remote_tokens": 200_000, "max_local_tokens": 0, "max_api_spend": 1.0, "max_wall_clock_s": 3600, "max_task_nodes": 1})
    gateway = ModelGateway(profile, budget)

    def decide(topic: str, question: str, options: list[str], facts: str) -> tuple[str, str] | None:
        prompt = (
            "You supervise an automated software factory. Choose exactly one option for this decision and say why in one sentence.\n"
            f"DECISION KIND: {topic}\nQUESTION: {question}\nOPTIONS: {', '.join(options)}\nWHAT THE TRACE SAYS:\n{facts}\n"
            'Reply with JSON only: {"choice": "<one option>", "reason": "<one sentence>"}.'
        )
        reply = gateway.model_for(cast(Any, "T3"), purpose="decision").invoke(prompt)
        text = str(getattr(reply, "content", reply))
        try:
            data = json.loads(text[text.find("{") : text.rfind("}") + 1])
        except ValueError:
            return None
        choice = str(data.get("choice", ""))
        return (choice, f"model: {data.get('reason', '')}") if choice in options else None

    return decide


def _read(project_root: Path, sql: str, args: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    conn = sqlite3.connect(f"file:{(project_root / '.factory' / 'state.db').as_posix()}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _status(project_root: Path) -> tuple[str, str]:
    try:
        rows = _read(project_root, "SELECT run_id, status FROM runs ORDER BY rowid DESC LIMIT 1")
    except sqlite3.Error:
        return "", ""
    return (str(rows[0]["run_id"]), str(rows[0]["status"])) if rows else ("", "")


def _pending(project_root: Path) -> list[sqlite3.Row]:
    try:
        return _read(project_root, "SELECT decision_id, topic, task_id, payload FROM decisions WHERE status = 'PENDING'")
    except sqlite3.Error:
        return []


def _facts_for(project_root: Path, task_id: str) -> str:
    path = project_root / ".factory" / "logs" / "trace.jsonl"
    if not task_id or not path.is_file():
        return "(no trace for this decision)"
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if task_id in raw and ('"turn"' in raw or '"attempt_end"' in raw or '"split_proposed"' in raw):
            try:
                row = json.loads(raw)
            except ValueError:
                continue
            data = row.get("data") or {}
            lines.append(f"{row.get('event')}: {str(data.get('message') or data.get('detail') or data.get('problems') or data.get('action'))[:200]}")
    return "\n".join(lines[-8:]) or "(nothing recorded yet)"


def _cli(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "asf", *args], cwd=project_root, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)  # noqa: S603


def drive(project_root: Path, spec_file: str, mode: str, profile: str, *, decider: Decider | None = None, resume_timeout_s: int = 1800, max_cycles: int = 20) -> tuple[Path, Path]:
    """Run the project unattended; return (REPORT.md, product.zip). Every decision goes through the model (if any), then the fixed policy, and is recorded."""
    from asf.m5_shared.gateway.gateway import ModelGateway

    profile = profile or ModelGateway.default_profile_name()
    replans: dict[str, int] = {}
    decide = decider
    if decide is None:
        try:
            decide = _model_decider(profile)
        except Exception as err:  # noqa: BLE001 - no model available: the fixed policy decides, and the record says so
            _record(project_root, {"decision": "(setup)", "by": "policy", "reason": f"the deciding model could not be set up: {err}"})
    if not _status(project_root)[0]:
        _cli(project_root, "run", "start", "--file", spec_file, "--mode", mode, "--profile", profile)
    for _ in range(max_cycles):
        run_id, status = _status(project_root)
        if status in _FINISHED:
            break
        before = (status, len(_pending(project_root)))
        _answer_all(project_root, decide, replans)
        out = project_root / ".factory" / "deliver"
        out.mkdir(parents=True, exist_ok=True)
        with (out / "resume_output.txt").open("a", encoding="utf-8") as log:
            proc = subprocess.Popen([sys.executable, "-m", "asf", "run", "resume", run_id], cwd=project_root, stdout=log, stderr=subprocess.STDOUT, text=True)  # noqa: S603
            started = time.monotonic()
            while proc.poll() is None and time.monotonic() - started < resume_timeout_s:
                time.sleep(6)
                _answer_all(project_root, decide, replans)
            if proc.poll() is None:
                proc.kill()
                _record(project_root, {"decision": "(run)", "by": "driver", "reason": f"the run process was stopped after {resume_timeout_s}s"})
        after = (_status(project_root)[1], len(_pending(project_root)))
        if after == before and after[1] == 0:
            _record(project_root, {"decision": "(run)", "by": "driver", "reason": "nothing changed in a full cycle; stopped and reported"})
            break
    report, archive = write_delivery(project_root)
    write_supervisor_notes(project_root, profile=profile)
    return report, archive


def _answer_all(project_root: Path, decide: Decider | None, replans: dict[str, int], skip: tuple[str, ...] = ()) -> None:
    for row in _pending(project_root):
        payload = json.loads(row["payload"])
        options = [str(o) for o in (payload.get("options") or [])]
        task_id = str(row["task_id"] or "")
        topic = str(row["topic"])
        if topic in skip:
            continue
        question = str(payload.get("question", ""))
        picked = None
        if decide is not None:
            try:
                picked = decide(topic, question, options, _facts_for(project_root, task_id))
            except Exception as err:  # noqa: BLE001 - a model failure falls back to the policy, and the record says so
                _record(project_root, {"decision": row["decision_id"], "note": f"the deciding model failed: {err}"})
        choice, reason = picked if picked is not None else choose_by_policy(options, replans.get(task_id, 0))
        if topic == "approve_plan" and "approve" in options and choice != "approve":
            # the plan already passed the planner's checks and its self-critique; a model's objection is recorded in full but does not end the run
            choice, reason = "approve", f"policy approved the plan although the model objected ({reason}); the objection is listed here so it is not lost"
        if choice == "replan" and replans.get(task_id, 0) >= MAX_REPLANS_PER_TASK:
            choice, reason = choose_by_policy([o for o in options if o != "replan"], 0)[0], "policy: the replan budget of this task is used; it is abandoned and reported"
        if choice == "replan":
            replans[task_id] = replans.get(task_id, 0) + 1
        _record(project_root, {"decision": str(row["decision_id"]), "topic": topic, "task": task_id, "question": question[:300], "options": options, "chosen": choice, "by": "model" if reason.startswith("model") else "policy", "reason": reason})
        _cli(project_root, "inbox", "answer", str(row["decision_id"]), "--choice", choice)
