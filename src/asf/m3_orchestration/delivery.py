# FILE: src/asf/m3_orchestration/delivery.py
# ROLE: Delivery: whatever the run produced, as one product.zip plus a REPORT.md listing every problem with its cause and a probable fix.
# ARCH REF: M3; p04 Escalation & Recovery (a run that cannot finish still hands over its work and an honest account)
# OWNS: REPORT.md content, the product archive
# DOES NOT OWN: Running tasks, the run's own report (run_graph.py), the trace format (m5_shared/trace.py)
# CONNECTS TO (external boundaries only):
#   - reads <project>/.factory/state.db (tasks table: task_id, state, title) read-only
#   - reads <project>/.factory/logs/trace.jsonl written by src/asf/m5_shared/trace.py (events of components scheduler, worker, decompose, run)
#   - called by src/asf/cli/commands/report.py: write_delivery
#   - called by tests/m3_orchestration/test_delivery.py: build_report, write_delivery
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Never put .env, .git, .factory, worktrees, blobs or caches into the archive.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/test_delivery.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/delivery.py` and `uv run mypy src/asf/m3_orchestration/delivery.py` are clean.

import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any

_SKIP_DIRS = {".git", ".factory", ".worktrees", ".asf_blobs", ".asf_locks", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "node_modules"}
_SKIP_FILES = {".env", "product.zip"}
_GOOD = {"VERIFIED", "INTEGRATED", "DECOMPOSED"}


def _tasks(project_root: Path) -> list[tuple[str, str, str]]:
    db = project_root / ".factory" / "state.db"
    if not db.is_file():
        return []
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=10)
    try:
        return [(str(r[0]), str(r[1]), str(r[2] or "")) for r in conn.execute("SELECT task_id, state, title FROM tasks ORDER BY created_at")]
    finally:
        conn.close()


def _trace(project_root: Path) -> list[dict[str, Any]]:
    path = project_root / ".factory" / "logs" / "trace.jsonl"
    rows: list[dict[str, Any]] = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def _facts(task_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """What the trace says about one task: attempts, helper use, the coder's last words, why a split failed."""
    facts: dict[str, Any] = {"attempts": 0, "helper": False, "messages": [], "failures": [], "split_problems": []}
    for row in rows:
        data = row.get("data") or {}
        event = row.get("event")
        if data.get("task") != task_id and row.get("task_id") != task_id:
            continue
        if event == "attempt_start":
            facts["attempts"] += 1
        elif event == "helper_model":
            facts["helper"] = True
        elif event == "turn" and data.get("action") in ("blocked", "done"):
            facts["messages"].append(f"{data.get('action')}: {str(data.get('message'))[:200]}")
        elif event == "attempt_end" and data.get("result") != "verified":
            facts["failures"].append(str(data.get("detail") or data.get("result"))[:200])
        elif event == "split_proposed" and data.get("problems"):
            facts["split_problems"] = [str(p)[:160] for p in data["problems"]]
    return facts


def _diagnosis(facts: dict[str, Any]) -> tuple[str, str]:
    """(cause, probable fix) from the evidence; a rule table, not a guess by a model."""
    text = " ".join([*facts["messages"], *facts["failures"], *facts["split_problems"]]).lower()
    if "not smaller enough" in text:
        return ("The task was too small to split further but the split rule demanded children under 80% of its size.", "Let a task at or below leaf size be accepted as it is; do not propose splits for it.")
    if "owned by both" in text or "outside the parent" in text:
        return ("The planner's split broke the file-ownership rules.", "Re-ask with the rule stated; allow sequential children to share one file.")
    if "blocked" in text and facts["attempts"] and not any(m.startswith("done") for m in facts["messages"]):
        return ("The coder gave up (answered blocked) instead of writing code.", "Show the coder the failing output and existing code; hand the task to the bigger model earlier.")
    if "local_bug" in text or "tests" in text and "fail" in text:
        return ("The code did not satisfy the acceptance tests after every attempt.", "Check whether the authored tests demand something the spec never asked for; if so fix the tests, otherwise split the task into smaller steps.")
    if "contract" in text:
        return ("The task's contract did not match what the tests or neighbours expect.", "Regenerate the contract and the tests from the same requirement text.")
    return ("The task did not reach a verified state; the trace holds no single clear reason.", "Read .factory/logs/trace.jsonl for this task id.")


def build_report(project_root: Path) -> str:
    """The REPORT.md text: a table of every task, then each problem with its evidence, cause and probable fix."""
    tasks = _tasks(project_root)
    rows = _trace(project_root)
    lines = ["# Delivery report", "", "## Tasks", "", "| task | state | attempts | bigger model used |", "|---|---|---|---|"]
    problems: list[tuple[str, str, dict[str, Any]]] = []
    for task_id, state, _title in tasks:
        facts = _facts(task_id, rows)
        lines.append(f"| {task_id} | {state} | {facts['attempts']} | {'yes' if facts['helper'] else 'no'} |")
        if state not in _GOOD:
            problems.append((task_id, state, facts))
    done = sum(1 for _, state, _ in tasks if state in ("VERIFIED", "INTEGRATED"))
    lines += ["", f"{done} of {len(tasks)} tasks are verified or integrated.", "", "## Problems", ""]
    if not problems:
        lines.append("None: every task is verified.")
    for task_id, state, facts in problems:
        cause, fix = _diagnosis(facts)
        lines += [f"### {task_id} ({state})", f"- Cause: {cause}", f"- Probable fix: {fix}"]
        lines += [f"- Evidence: {item}" for item in [*facts["messages"][-3:], *facts["failures"][-2:], *facts["split_problems"][:2]]]
        lines.append("")
    lines += ["## What is in the archive", "", "The project files as they are now (no secrets, no run data). Tasks listed above as problems may be missing or incomplete.", ""]
    return "\n".join(lines)


def write_delivery(project_root: Path) -> tuple[Path, Path]:
    """Write REPORT.md and product.zip under <project>/.factory/deliver/ and return (report, archive). The report is also inside the archive."""
    out = project_root / ".factory" / "deliver"
    out.mkdir(parents=True, exist_ok=True)
    report = out / "REPORT.md"
    report.write_text(build_report(project_root), encoding="utf-8")
    archive = out / "product.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(project_root.rglob("*")):
            rel = path.relative_to(project_root)
            if not path.is_file() or path.name in _SKIP_FILES or path.suffix == ".pyc" or path.name.startswith("AUTOPILOT") or any(part in _SKIP_DIRS for part in rel.parts):
                continue
            bundle.write(path, rel.as_posix())
        bundle.write(report, "REPORT.md")
    return report, archive
