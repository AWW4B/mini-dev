# FILE: tests/m3_orchestration/decomposition/test_decomposition_graph.py
# ROLE: Tests that prove src/asf/m3_orchestration/decomposition/decomposition_graph.py meets its DONE WHEN conditions.
# ARCH REF: M3; p05; IF-07a; IF-09; IF-10; IF-10b; D-06; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/decomposition/decomposition_graph.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/decomposition/decomposition_graph.py: build_decomposition_graph (unit under test)
#   - imports from src/asf/m3_orchestration/decomposition/frontier.py: Frontier (the persisted work-list)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/decomposition/test_decomposition_graph.py` on Windows and Linux once src/asf/m3_orchestration/decomposition/decomposition_graph.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/decomposition/test_decomposition_graph.py` and `uv run mypy tests/m3_orchestration/decomposition/test_decomposition_graph.py` are clean.

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from asf.m3_orchestration.decomposition.decomposition_graph import build_decomposition_graph
from asf.m3_orchestration.decomposition.frontier import Frontier


def _node(node_id: str, parent: str | None = "run1-root", **over: Any) -> dict[str, Any]:
    base = {
        "id": node_id, "run_id": "run1", "parent_id": parent, "kind": "composite", "goal": f"implement {node_id} with care and detail",
        "idempotency_key": f"k-{node_id}", "depth": 1, "acceptance_refs": [f"tests/test_{node_id.split('-')[-1]}.py::test_ok"],
        "allowed_files": [f"src/{node_id.split('-')[-1]}.py"],
    }
    return {**base, **over}


def _plan(*modules: dict[str, Any]) -> dict[str, Any]:
    return {"run_id": "run1", "root": _node("run1-root", None, depth=0, allowed_files=[], acceptance_refs=[]), "module_nodes": list(modules), "shared_type_nodes": [], "contract_ids": []}


PROFILE = SimpleNamespace(c_eff_tokens=10_000)


class _Scheduler:
    def __init__(self) -> None:
        self.specs: list[Any] = []

    def enqueue(self, spec: Any) -> None:
        self.specs.append(spec)


class _Broker:
    def __init__(self) -> None:
        self.requests: list[Any] = []

    def request(self, req: Any) -> None:
        self.requests.append(req)


class _Gateway:
    """T3 splitter: answers with the scripted split for the node being split; T1 rubric: low scores."""

    def __init__(self, splits: dict[str, list[dict[str, Any]]] | None = None, ambiguity: float = 0.1) -> None:
        self.splits = {k: list(v) for k, v in (splits or {}).items()}
        self.ambiguity = ambiguity
        self.split_calls: list[tuple[str, Any]] = []

    def model_for(self, role: Any, purpose: str, output_schema: Any = None, task_id: Any = None) -> Any:
        outer = self

        class _Model:
            def invoke(self, prompt: str) -> Any:
                if purpose == "rubric":
                    return {"ambiguity": outer.ambiguity, "coupling": 0.1, "notes": "scripted"}
                outer.split_calls.append((str(task_id), role))
                return outer.splits[str(task_id)].pop(0)

        return _Model()


def _run(plan: dict[str, Any], tmp_path: Path, gateway: _Gateway | None = None, frontier: Frontier | None = None, **deps: Any) -> dict[str, Any]:
    graph = build_decomposition_graph(None)
    config: Any = {
        "configurable": {
            "frontier": frontier if frontier is not None else Frontier("run1"), "profile": PROFILE, "gateway": gateway or _Gateway(), "scheduler": deps.pop("scheduler", _Scheduler()),
            "authoring": lambda node: [f"tests/test_{str(node.id).split('-')[-1]}.py"], **deps,
        }
    }
    out: dict[str, Any] = graph.invoke({"plan": plan, "requirement_ids": deps.get("requirement_ids", [])}, config)
    return out


def test_small_modules_are_certified_as_leaves_and_handed_to_the_scheduler(tmp_path: Path) -> None:
    scheduler = _Scheduler()
    out = _run(_plan(_node("run1-a"), _node("run1-b")), tmp_path, scheduler=scheduler, base_commit="abc", parent_branch="main")
    assert sorted(out["leaves"]) == ["run1-a", "run1-b"]
    assert [s.task_id for s in scheduler.specs] == ["run1-a", "run1-b"]
    assert scheduler.specs[0].base_commit == "abc" and scheduler.specs[0].allowed_files == ["src/a.py"]
    report = out["report"]
    assert report["complete"] is True and report["suspended_nodes"] == [] and report["run_id"] == "run1"


def test_shared_type_leaves_are_expanded_first(tmp_path: Path) -> None:
    plan = _plan(_node("run1-a"))
    plan["shared_type_nodes"] = [_node("run1-types", kind="shared_types")]
    scheduler = _Scheduler()
    _run(plan, tmp_path, scheduler=scheduler, batch_size=1)
    assert [s.task_id for s in scheduler.specs] == ["run1-types", "run1-a"]


def test_a_node_that_is_too_big_is_split_and_its_children_are_certified(tmp_path: Path) -> None:
    big = _node("run1-big", allowed_files=["src/a.py", "src/b.py", "src/c.py", "src/d.py"], acceptance_refs=["tests/test_a.py::t1", "tests/test_c.py::t2"])
    split = {
        "children": [
            {"goal": "implement the first half carefully", "allowed_files": ["src/a.py", "src/b.py"], "acceptance_refs": ["tests/test_a.py::t1"]},
            {"goal": "implement the second half carefully", "allowed_files": ["src/c.py", "src/d.py"], "acceptance_refs": ["tests/test_c.py::t2"], "deps": [1]},
        ],
        "rationale": "halves",
    }
    gateway, scheduler = _Gateway({"run1-big": [split]}), _Scheduler()
    out = _run(_plan(big), tmp_path, gateway, scheduler=scheduler)
    assert sorted(out["leaves"]) == ["run1-big.1", "run1-big.2"]
    assert [s.task_id for s in scheduler.specs] == ["run1-big.1", "run1-big.2"]
    assert gateway.split_calls == [("run1-big", "T3")]
    assert out["nodes_created"] == 3 and out["report"]["complete"] is True


def test_an_invalid_split_is_fed_back_and_retried(tmp_path: Path) -> None:
    big = _node("run1-big", allowed_files=["src/a.py", "src/b.py", "src/c.py", "src/d.py"], acceptance_refs=["tests/test_a.py::t1", "tests/test_c.py::t2"])
    bad = {"children": [{"goal": "only one child", "allowed_files": ["src/a.py"], "acceptance_refs": ["tests/test_a.py::t1"]}]}
    good = {
        "children": [
            {"goal": "implement the first half carefully", "allowed_files": ["src/a.py", "src/b.py"], "acceptance_refs": ["tests/test_a.py::t1"]},
            {"goal": "implement the second half carefully", "allowed_files": ["src/c.py", "src/d.py"], "acceptance_refs": ["tests/test_c.py::t2"]},
        ]
    }
    gateway = _Gateway({"run1-big": [bad, good]})
    out = _run(_plan(big), tmp_path, gateway)
    assert len(gateway.split_calls) == 2 and sorted(out["leaves"]) == ["run1-big.1", "run1-big.2"]


def test_when_no_valid_split_is_found_the_node_is_escalated_to_the_user(tmp_path: Path) -> None:
    big = _node("run1-big", allowed_files=["src/a.py", "src/b.py", "src/c.py", "src/d.py"])
    bad = {"children": [{"goal": "only one child", "allowed_files": ["src/a.py"]}]}
    broker = _Broker()
    out = _run(_plan(big), tmp_path, _Gateway({"run1-big": [bad, bad, bad]}), decision_broker=broker)
    assert out["suspended"] == ["run1-big"] and out["report"]["complete"] is False
    (req,) = broker.requests
    assert req.kind.value == "manual_split" and "accept_larger_leaf" in req.options and req.task_id == "run1-big"


def test_the_last_split_attempt_uses_the_higher_tier(tmp_path: Path) -> None:
    big = _node("run1-big", allowed_files=["src/a.py", "src/b.py", "src/c.py", "src/d.py"])
    bad = {"children": [{"goal": "only one child", "allowed_files": ["src/a.py"]}]}
    gateway = _Gateway({"run1-big": [bad, bad, bad]})
    _run(_plan(big), tmp_path, gateway)
    assert [role for _, role in gateway.split_calls] == ["T3", "T3", "reviewer"]


def test_an_ambiguous_node_waits_for_an_answer_while_siblings_continue(tmp_path: Path) -> None:
    broker, scheduler = _Broker(), _Scheduler()

    class _Mixed(_Gateway):
        def model_for(self, role: Any, purpose: str, output_schema: Any = None, task_id: Any = None) -> Any:
            if purpose == "rubric":
                return SimpleNamespace(invoke=lambda prompt: {"ambiguity": 0.95 if "implement run1-vague" in prompt else 0.1, "coupling": 0.1, "notes": "scripted"})
            return super().model_for(role, purpose, output_schema, task_id)

    out = _run(_plan(_node("run1-vague"), _node("run1-clear")), tmp_path, _Mixed(), scheduler=scheduler, decision_broker=broker)
    assert out["leaves"] == ["run1-clear"] and out["suspended"] == ["run1-vague"]
    assert broker.requests[0].kind.value == "clarify" and out["report"]["complete"] is False


def test_lazy_expansion_defers_nodes_until_their_dependencies_are_verified(tmp_path: Path) -> None:
    frontier, scheduler = Frontier("run1"), _Scheduler()
    plan = _plan(_node("run1-a"), _node("run1-b", deps=["run1-a"]))
    out = _run(plan, tmp_path, frontier=frontier, scheduler=scheduler, lazy=True)
    assert out["leaves"] == ["run1-a"] and out["report"]["suspended_nodes"] == ["run1-b"] and out["report"]["complete"] is False
    assert frontier.wake_dependents("run1-a") == 1

    graph = build_decomposition_graph(None)
    config: Any = {"configurable": {"frontier": frontier, "profile": PROFILE, "gateway": _Gateway(), "scheduler": scheduler, "authoring": lambda n: ["tests/test_b.py"], "lazy": True}}
    again = graph.invoke({"plan": plan, "seeded": True}, config)
    assert again["leaves"] == ["run1-b"] and again["report"]["complete"] is True


def test_a_pause_stops_the_loop_between_batches(tmp_path: Path) -> None:
    calls: list[int] = []

    def control() -> str | None:
        calls.append(1)
        return "pause" if len(calls) > 1 else None

    out = _run(_plan(_node("run1-a"), _node("run1-b"), _node("run1-c")), tmp_path, batch_size=1, control=control)
    assert out["stop"] == "pause" and out["leaves"] == ["run1-a"]
    assert out["report"]["complete"] is False


def test_the_node_budget_stops_the_run(tmp_path: Path) -> None:
    out = _run(_plan(_node("run1-a"), _node("run1-b"), _node("run1-c")), tmp_path, batch_size=1, max_nodes=3)
    assert out["stop"] == "budget" and out["report"]["complete"] is False


def test_requirements_that_no_node_mentions_are_reported_untraced(tmp_path: Path) -> None:
    plan = _plan(_node("run1-a", acceptance_refs=["tests/test_a.py::test_ok covers REQ-1"]))
    out = _run(plan, tmp_path, requirement_ids=["REQ-1", "REQ-2"])
    assert out["report"]["untraced_requirements"] == ["REQ-2"] and out["report"]["complete"] is False


def test_missing_collaborators_are_reported_clearly() -> None:
    graph = build_decomposition_graph(None)
    with pytest.raises(RuntimeError, match="frontier"):
        graph.invoke({"plan": _plan()}, {"configurable": {}})
    with pytest.raises(RuntimeError, match="profile"):
        graph.invoke({"plan": _plan()}, {"configurable": {"frontier": Frontier("run1")}})
