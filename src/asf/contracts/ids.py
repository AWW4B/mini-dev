# FILE: src/asf/contracts/ids.py
# ROLE: Defines the typed identifiers shared by all contracts.
# ARCH REF: p15
# OWNS: Identifier types and the id factory signature
# DOES NOT OWN: Storage of ids
# CONNECTS TO (external boundaries only):
#   - called by src/asf/contracts/events.py: EventId, RunId, TaskId
#   - called by src/asf/contracts/tasks.py: AttemptId, LeaseId, RunId, TaskId
#   - called by src/asf/contracts/contract_spec.py: ContractId, TaskId
#   - called by src/asf/contracts/context.py: TaskId
#   - called by src/asf/contracts/decisions.py: DecisionId, RunId, TaskId
#   - called by src/asf/contracts/requests.py: ProjectId
#   - called by src/asf/contracts/control.py: CommandId, RunId, TaskId
#   - called by src/asf/contracts/models.py: LeaseId
#   - called by src/asf/contracts/tools.py: TaskId
#   - called by src/asf/contracts/workspace.py: TaskId
#   - called by src/asf/contracts/metrics.py: RunId, TaskId
#   - called by src/asf/contracts/outcomes.py: RunId, TaskId
#   - called by src/asf/contracts/budget.py: RunId
#   - called by src/asf/contracts/history.py: ProjectId, RunId
#   - called by tests/contracts/test_ids.py: new_id, ProjectId, RunId, TaskId, AttemptId, EventId, DecisionId, LeaseId, CommandId, ContractId
#   - called by src/asf/m3_orchestration/run_graph.py: new_id
#   - called by src/asf/cli/run_controls.py: new_id
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. This file is declarations only: Pydantic models, enums and type aliases. Add field validators only where the docstring of a field states a constraint.
#   6. Every model must round-trip through model_dump_json() / model_validate_json() unchanged; the JSON Schema exported from these models is the published contract (D-39: no hand-written JSON).
#   7. Changing a field name or type is a contract change: stop and report instead.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; business logic; I/O; imports from asf.m1-m5 packages, asf.cli, asf.web or asf.platform
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/contracts/test_ids.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/contracts/ids.py` and `uv run mypy src/asf/contracts/ids.py` are clean.

import os
import time
from typing import NewType

ProjectId = NewType("ProjectId", str)
RunId = NewType("RunId", str)
TaskId = NewType("TaskId", str)
AttemptId = NewType("AttemptId", str)
EventId = NewType("EventId", str)
DecisionId = NewType("DecisionId", str)
LeaseId = NewType("LeaseId", str)
CommandId = NewType("CommandId", str)
ContractId = NewType("ContractId", str)


def new_id(prefix: str) -> str:
    """Return a new unique, sortable id string such as 'task_01J...' (UUIDv7 or ULID text).

    Uses a millisecond-precision timestamp (48 bits) + 80 bits of randomness,
    encoded as a 26-char Crockford Base32 string (ULID format), prefixed with
    ``<prefix>_``.  The result is lexicographically sortable by creation time.
    """
    # ULID: 48-bit ms timestamp + 80-bit random, Crockford Base32
    _ENCODING = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

    ts_ms = int(time.time() * 1000) & 0xFFFF_FFFF_FFFF  # 48 bits
    rand = int.from_bytes(os.urandom(10), "big")  # 80 bits

    combined = (ts_ms << 80) | rand  # 128 bits total

    chars: list[str] = []
    for _ in range(26):
        chars.append(_ENCODING[combined & 0x1F])
        combined >>= 5
    ulid = "".join(reversed(chars))

    return f"{prefix}_{ulid}"
