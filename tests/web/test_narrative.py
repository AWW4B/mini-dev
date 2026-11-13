# FILE: tests/web/test_narrative.py
# ROLE: Tests that prove src/asf/web/narrative.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02 Active Group Chat; p15 EventEnvelope; IF-18; D-14b narrative amendment; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/web/narrative.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/web/narrative.py: NarrativeItem, Handoff, build_narrative, derive_handoffs (unit under test)
#   - imports from src/asf/contracts/events.py: EventEnvelope (event fixtures)
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use the tmp_path fixture or the fake_paths fixture for every filesystem location.
#   6. Use the fakes from tests/conftest.py instead of real GPUs, networks, sandboxes or model providers unless the test is marked needs_gpu, needs_network or needs_sandbox.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; real API keys; network access in unmarked tests; sleeping for timing (use the fake clock)
# ERRORS: Failures surface as pytest assertion failures.
# DONE WHEN: (1) All tests pass via `uv run pytest tests/web/test_narrative.py` on Windows and Linux once src/asf/web/narrative.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/web/test_narrative.py` and `uv run mypy tests/web/test_narrative.py` are clean.

from typing import Any

from asf.contracts.events import EventEnvelope
from asf.web.narrative import Handoff, NarrativeItem, build_narrative, derive_handoffs


def _event(event_id: str, kind: str, seq: int, payload: dict[str, Any] | None = None, actor: str = "Worker 1", **over: Any) -> EventEnvelope:
    return EventEnvelope.model_validate(
        {
            "event_id": event_id, "run_id": "r1", "seq": seq, "ts": "2026-11-12T10:00:00+00:00",
            "actor": {"kind": "agent", "role": over.pop("role", "worker"), "name": actor}, "kind": kind, "correlation_id": "c",
            "payload": payload or {}, **over,
        }
    )


def test_models() -> None:
    item = NarrativeItem(seq=1, participant="W", kind="task_received", summary="s")
    assert item.detail_ref is None and item.internal is False
    assert Handoff(from_participant="a", to_participant="b", task_id=None, sent_seq=1, received_seq=None).received_seq is None


def test_each_narrative_kind_has_a_template_over_its_payload() -> None:
    events = [
        _event("e1", "task_received", 1, {"goal_summary": "write billing", "from_role": "scheduler"}),
        _event("e2", "step_started", 2, {"step_no": 3, "strategy": "tool_loop", "summary": "editing"}),
        _event("e3", "tool_called", 3, {"tool": "write_file", "args_summary": "src/a.py", "status": "approved", "sandbox_tier": "A", "reason": "implement it", "via_code_exec": True}),
        _event("e4", "tool_result", 4, {"tool": "write_file", "summary": "ok", "duration_ms": 12, "exit_status": 0, "output_ref": "sha256:" + "a" * 64}),
        _event("e5", "handoff_sent", 5, {"to_role": "gate", "summary": "1 file changed"}),
        _event("e6", "handoff_received", 6, {"summary": "got the change set"}, actor="Gate"),
        _event("e7", "gate_result", 7, {"passed": False, "failure_class": "LOCAL_BUG", "summary": "2 tests failed"}, actor="Gate"),
        _event("e8", "decision_needed", 8, {"decision_id": "d1", "kind": "clarify", "question": "Which database?"}),
    ]
    summaries = [i.summary for i in build_narrative(events)]
    assert summaries == [
        "received a task from scheduler: write billing",
        "started step 3 (tool_loop): editing",
        "called write_file via code (src/a.py) because implement it: approved, sandbox A",
        "write_file finished in 12 ms, exit 0: ok",
        "handed over to gate: 1 file changed",
        "received the hand-off: got the change set",
        "gate failed (LOCAL_BUG): 2 tests failed",
        "needs a decision (clarify): Which database?",
    ]


def test_items_are_in_seq_order_even_when_given_out_of_order() -> None:
    events = [_event("e2", "step_started", 2), _event("e1", "task_received", 1)]
    assert [i.seq for i in build_narrative(events)] == [1, 2]


def test_plumbing_events_are_not_part_of_the_story() -> None:
    events = [_event("e1", "usage", 1), _event("e2", "model_call", 2), _event("e3", "state_changed", 3), _event("e4", "task_received", 4)]
    assert [i.kind for i in build_narrative(events)] == ["task_received"]


def test_internal_events_are_flagged() -> None:
    items = build_narrative([_event("e1", "tool_result", 1, {"tool": "t", "duration_ms": 1, "summary": "x"}, visibility="internal"), _event("e2", "tool_result", 2, {"tool": "t"})])
    assert [i.internal for i in items] == [True, False]


def test_missing_payload_fields_do_not_crash_the_narrative() -> None:
    (item,) = build_narrative([_event("e1", "gate_result", 1)])
    assert item.summary == "gate failed"
    (item2,) = build_narrative([_event("e2", "tool_called", 1)])
    assert "called ?" in item2.summary


def test_text_is_redacted_before_it_reaches_the_viewer() -> None:
    sample = "sk-abcdefghijklmnopqrstuvwxyz0123"
    events = [_event("e1", "task_received", 1, {"goal_summary": f"use key {sample}", "from_role": "user"}, actor=f"Agent {sample}")]
    (item,) = build_narrative(events)
    assert sample not in item.summary and sample not in item.participant


def test_markup_in_event_text_is_left_for_the_browser_to_escape() -> None:
    (item,) = build_narrative([_event("e1", "task_received", 1, {"goal_summary": "<script>alert(1)</script>", "from_role": "x"})])
    assert "<script>alert(1)</script>" in item.summary  # escaping is the browser's job (textContent) and the JSON encoder's


def test_a_detail_link_comes_from_the_payload() -> None:
    items = build_narrative(
        [
            _event("e1", "tool_result", 1, {"tool": "t", "output_ref": "sha256:" + "b" * 64}),
            _event("e2", "gate_result", 2, {"passed": True, "report_ref": "sha256:" + "c" * 64}),
            _event("e3", "step_started", 3, {}, payload_ref="sha256:" + "d" * 64),
            _event("e4", "task_received", 4, {}),
        ]
    )
    assert [i.detail_ref for i in items] == ["sha256:" + "b" * 64, "sha256:" + "c" * 64, "sha256:" + "d" * 64, None]


def test_handoffs_pair_by_causation_id_not_by_position() -> None:
    events = [
        _event("s1", "handoff_sent", 1, {"to_role": "gate"}, task_id="t1"),
        _event("s2", "handoff_sent", 2, {"to_role": "scheduler"}, actor="Gate"),
        _event("r2", "handoff_received", 3, {}, actor="Scheduler", causation_id="s2"),
        _event("r1", "handoff_received", 4, {}, actor="Gate", causation_id="s1"),
    ]
    first, second = derive_handoffs(events)
    assert (first.from_participant, first.to_participant, first.task_id, first.sent_seq, first.received_seq) == ("Worker 1", "Gate", "t1", 1, 4)
    assert (second.from_participant, second.to_participant, second.sent_seq, second.received_seq) == ("Gate", "Scheduler", 2, 3)


def test_an_unreceived_handoff_stays_open_and_names_the_target_role() -> None:
    (h,) = derive_handoffs([_event("s1", "handoff_sent", 1, {"to_role": "gate"})])
    assert h.received_seq is None and h.to_participant == "gate"


def test_a_received_event_without_a_matching_send_is_ignored() -> None:
    assert derive_handoffs([_event("r1", "handoff_received", 1, {}, causation_id="ghost")]) == []
