# FILE: tests/m3_orchestration/decomposition/test_rubric.py
# ROLE: Tests that prove src/asf/m3_orchestration/decomposition/rubric.py meets its DONE WHEN conditions.
# ARCH REF: M3; p05 T1 rubric; D-09 tiny-model tasks; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/decomposition/rubric.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/decomposition/rubric.py: RubricScore, score_node (unit under test)
#   - imports from src/asf/contracts/tasks.py: TaskNode (node fixtures)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/decomposition/test_rubric.py` on Windows and Linux once src/asf/m3_orchestration/decomposition/rubric.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/decomposition/test_rubric.py` and `uv run mypy tests/m3_orchestration/decomposition/test_rubric.py` are clean.

from types import SimpleNamespace
from typing import Any

from asf.contracts.tasks import TaskNode
from asf.m3_orchestration.decomposition.rubric import RubricScore, score_node


def _node(**over: object) -> TaskNode:
    base = {
        "id": "t1", "run_id": "r1", "kind": "composite", "goal": "implement the refund endpoint with validation",
        "idempotency_key": "k", "acceptance_refs": ["refund returns a receipt"], "allowed_files": ["src/refund.py"],
    }
    return TaskNode.model_validate({**base, **over})


class _Gateway:
    def __init__(self, reply: Any) -> None:
        self.reply = reply
        self.calls: list[tuple[Any, str]] = []

    def model_for(self, role: Any, purpose: str, output_schema: Any = None, task_id: Any = None) -> Any:
        self.calls.append((role, purpose))
        outer = self

        class _Model:
            def invoke(self, prompt: str) -> Any:
                if isinstance(outer.reply, Exception):
                    raise outer.reply
                return outer.reply

        return _Model()


def test_without_a_gateway_the_rubric_is_deterministic() -> None:
    a, b = score_node(_node()), score_node(_node())
    assert a == b and a.notes.startswith("deterministic")
    assert 0.0 <= a.ambiguity <= 1.0 and 0.0 <= a.coupling <= 1.0


def test_vague_short_untested_goals_score_as_more_ambiguous() -> None:
    clear = score_node(_node())
    vague = score_node(_node(goal="do stuff etc", acceptance_refs=[]))
    assert vague.ambiguity > clear.ambiguity
    assert "no acceptance criteria" in vague.notes and "vague wording" in vague.notes


def test_coupling_grows_with_dependencies_contracts_and_files() -> None:
    low = score_node(_node())
    high = score_node(_node(deps=["a", "b", "c"], contract_refs=["x@1", "y@1"], allowed_files=["a.py", "b.py", "c.py"]))
    assert high.coupling > low.coupling and high.coupling <= 1.0


def test_t1_is_asked_with_the_rubric_schema_and_its_scores_are_clamped() -> None:
    gateway = _Gateway(RubricScore(ambiguity=1.7, coupling=-0.3, notes="odd"))
    score = score_node(_node(), gateway=gateway)  # type: ignore[arg-type]
    assert (score.ambiguity, score.coupling, score.notes) == (1.0, 0.0, "odd")
    assert gateway.calls == [("T1", "rubric")]


def test_a_dict_reply_is_accepted() -> None:
    score = score_node(_node(), gateway=_Gateway({"ambiguity": 0.4, "coupling": 0.1, "notes": "fine"}))  # type: ignore[arg-type]
    assert score.ambiguity == 0.4


def test_a_reply_outside_the_schema_falls_back_to_the_deterministic_rubric() -> None:
    score = score_node(_node(), gateway=_Gateway({"nonsense": True}))  # type: ignore[arg-type]
    assert score.notes.startswith("deterministic")
    assert score_node(_node(), gateway=_Gateway(SimpleNamespace(content="not json"))).notes.startswith("deterministic")  # type: ignore[arg-type]


def test_a_failing_model_falls_back_too() -> None:
    assert score_node(_node(), gateway=_Gateway(RuntimeError("provider down"))).notes.startswith("deterministic")  # type: ignore[arg-type]
