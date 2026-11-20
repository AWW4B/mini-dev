# FILE: src/asf/m3_orchestration/supervisor.py
# ROLE: Supervisor: reads the history of runs and writes what should change in the system itself, ranked by how often the problem came back.
# ARCH REF: M3; p04 Escalation & Recovery (learning from past runs)
# OWNS: SUPERVISOR.md content, the per-project history of problems (supervisor_history.jsonl)
# DOES NOT OWN: Changing code or configuration (it only proposes; a person or a coding session applies the change), the delivery report (delivery.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/delivery.py: diagnose_project (the problems of this run with cause and fix)
#   - called by src/asf/m3_orchestration/autonomy.py: write_supervisor_notes
#   - called by tests/m3_orchestration/test_supervisor.py: write_supervisor_notes
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Propose, never apply: nothing outside .factory/ is written, and the file says so.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m3_orchestration/test_supervisor.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m3_orchestration/supervisor.py` and `uv run mypy src/asf/m3_orchestration/supervisor.py` are clean.

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from asf.m3_orchestration.delivery import diagnose_project


def write_supervisor_notes(project_root: Path) -> Path:
    """Append this run's problems to the history and write SUPERVISOR.md: each recurring cause, how many times it was seen, and the change proposed."""
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
        "These are proposals read from the history of this project's runs. Nothing was changed: a person or a coding session applies them.",
        "",
        f"Problems recorded so far: {sum(seen.values())}; in this run: {len(problems)}.",
        "",
        "## Proposed changes, most frequent first",
        "",
    ]
    if not seen:
        lines.append("None: no task has failed in the recorded history.")
    for (cause, fix), count in seen.most_common():
        lines += [f"### Seen {count} time(s)", f"- Cause: {cause}", f"- Proposed change: {fix}", ""]
    target = project_root / ".factory" / "deliver" / "SUPERVISOR.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    return target
