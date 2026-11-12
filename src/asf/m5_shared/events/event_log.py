# FILE: src/asf/m5_shared/events/event_log.py
# ROLE: Appends EventEnvelopes to the events table and reads them back by run and seq cursor.
# ARCH REF: M5; p10 Event Stream; IF-17 EventPublish; IF-18 EventSubscribe; D-23; D-14b
# OWNS: The events table contents, seq assignment, blob offload for payloads over 8 KB
# DOES NOT OWN: Fan-out to live subscribers (fanout.py); rendering (cli views, web)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/events.py: EventEnvelope, Visibility (IF-17 shape)
#   - imports from src/asf/m5_shared/events/redaction.py: redact_payload (redaction)
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (large payloads)
#   - called by src/asf/m5_shared/state_store/outbox.py: EventLog
#   - called by src/asf/m5_shared/events/fanout.py: EventLog
#   - called by src/asf/cli/commands/events.py: EventLog
#   - called by src/asf/web/projection.py: EventLog
#   - called by tests/m5_shared/events/test_event_log.py: EventLog
#   - called by src/asf/cli/views/trace_view.py: EventLog
#   - called by tests/cli/views/test_trace_view.py: EventLog
#   - called by src/asf/m3_orchestration/run_graph.py: EventLog
#   - emits/consumes: stores EventEnvelope (all EventKind values incl. narrative kinds); serves them ordered by seq
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. seq is monotonic per run and assigned inside the append transaction; append is idempotent on event_id.
#   9. Always redact payloads before storing.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/events/test_event_log.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/events/event_log.py` and `uv run mypy src/asf/m5_shared/events/event_log.py` are clean.

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from asf.contracts.events import EventEnvelope, Visibility
from asf.m5_shared.events.redaction import redact_payload
from asf.m5_shared.workspace.blobs import BlobStore


class EventLog:
    conn: sqlite3.Connection
    blobs: BlobStore | None

    def __init__(self, conn: sqlite3.Connection | Path | str, blobs: BlobStore | None = None) -> None:
        if isinstance(conn, (Path, str)):
            self.conn = sqlite3.connect(str(conn), autocommit=False)
        else:
            self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self.blobs = blobs

    def append(self, events: Sequence[EventEnvelope]) -> list[int]:
        """Store events (idempotent on event_id); return assigned seq numbers."""
        assigned_seqs: list[int] = []

        with self.conn:
            for event in events:
                event_id = str(event.event_id)
                run_id = str(event.run_id)

                # Check if already present (idempotent)
                cur = self.conn.execute("SELECT seq FROM events WHERE event_id = ?", (event_id,))
                row = cur.fetchone()
                if row is not None:
                    assigned_seqs.append(int(row["seq"]))
                    continue

                # Monotonic sequence per run
                cur = self.conn.execute(
                    "SELECT coalesce(max(seq), 0) FROM events WHERE run_id = ?",
                    (run_id,),
                )
                max_seq_row = cur.fetchone()
                next_seq = (int(max_seq_row[0]) if max_seq_row else 0) + 1

                # Redact payload
                clean_payload = redact_payload(event.payload)
                payload_bytes = json.dumps(clean_payload).encode("utf-8")
                payload_ref = getattr(event, "payload_ref", None)
                stored_payload = clean_payload

                # Offload to blobs if payload > 8 KB
                if len(payload_bytes) > 8192 and self.blobs is not None:
                    payload_ref = self.blobs.put(payload_bytes)
                    stored_payload = {}

                if isinstance(event, EventEnvelope):
                    stored_envelope = event.model_copy(
                        update={
                            "seq": next_seq,
                            "payload": stored_payload,
                            "payload_ref": payload_ref,
                            "redacted": True,
                        }
                    )
                else:
                    actor_data = (
                        event.actor
                        if isinstance(event.actor, dict)
                        else vars(event.actor)
                        if hasattr(event.actor, "__dict__")
                        else event.actor
                    )
                    stored_envelope = EventEnvelope.model_validate(
                        {
                            "event_id": event_id,
                            "run_id": run_id,
                            "task_id": getattr(event, "task_id", None),
                            "seq": next_seq,
                            "ts": event.ts,
                            "actor": actor_data,
                            "kind": event.kind.value if hasattr(event.kind, "value") else str(event.kind),
                            "causation_id": getattr(event, "causation_id", None),
                            "correlation_id": getattr(event, "correlation_id", ""),
                            "payload": stored_payload,
                            "payload_ref": payload_ref,
                            "visibility": (
                                event.visibility.value if hasattr(event.visibility, "value") else str(event.visibility)
                            ),
                            "redacted": True,
                        }
                    )

                envelope_json = stored_envelope.model_dump_json()
                kind_val = stored_envelope.kind.value
                vis_val = stored_envelope.visibility.value
                ts_str = stored_envelope.ts.isoformat()
                source = stored_envelope.actor.role
                task_id = stored_envelope.task_id

                self.conn.execute(
                    "INSERT INTO events (event_id, run_id, seq, timestamp, kind, visibility, source, "
                    "task_id, attempt_id, blob_ref, payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        event_id,
                        run_id,
                        next_seq,
                        ts_str,
                        kind_val,
                        vis_val,
                        source,
                        task_id,
                        None,
                        payload_ref,
                        envelope_json,
                    ),
                )
                assigned_seqs.append(next_seq)

        return assigned_seqs

    def read(
        self,
        run_id: str,
        after_seq: int = 0,
        limit: int = 500,
        visibility: Visibility | None = None,
    ) -> list[EventEnvelope]:
        sql = "SELECT payload FROM events WHERE run_id = ? AND seq > ?"
        params: list[Any] = [run_id, after_seq]
        if visibility is not None:
            vis_val = visibility.value if hasattr(visibility, "value") else str(visibility)
            sql += " AND visibility = ?"
            params.append(vis_val)
        sql += " ORDER BY seq ASC LIMIT ?"
        params.append(limit)

        cur = self.conn.execute(sql, params)
        return [EventEnvelope.model_validate_json(row["payload"]) for row in cur.fetchall()]

    def latest_seq(self, run_id: str) -> int:
        cur = self.conn.execute(
            "SELECT coalesce(max(seq), 0) FROM events WHERE run_id = ?",
            (run_id,),
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0
