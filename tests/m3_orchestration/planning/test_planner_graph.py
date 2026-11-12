# FILE: tests/m3_orchestration/planning/test_planner_graph.py
# ROLE: Tests that prove src/asf/m3_orchestration/planning/planner_graph.py meets its DONE WHEN conditions.
# ARCH REF: M3; p04 Planning Agent; IF-07; IF-07a ApprovedPlan; A-1; A-2; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m3_orchestration/planning/planner_graph.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m3_orchestration/planning/planner_graph.py: build_planner_graph, check_plan, plan_result, PlanModel (unit under test)
#   - imports from src/asf/contracts/errors.py: ProviderUnavailable (fake gateway failure)
#   - imports from src/asf/contracts/requests.py: StructuredRequest (check_plan input)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/planning/test_planner_graph.py` on Windows and Linux once src/asf/m3_orchestration/planning/planner_graph.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/planning/test_planner_graph.py` and `uv run mypy tests/m3_orchestration/planning/test_planner_graph.py` are clean.

from types import SimpleNamespace
from typing import Any

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from asf.contracts.errors import ProviderUnavailable
from asf.contracts.requests import StructuredRequest
from asf.m3_orchestration.planning.planner_graph import PlanModel, build_planner_graph, check_plan, plan_result


def _request(task_type: str = "new_build", reqs: tuple[str, ...] = ("REQ-1", "REQ-2")) -> dict[str, Any]:
    return {
        "request_id": "q1", "project_id": "p", "task_type": task_type,
        "requirements": [{"req_id": r, "text": f"do {r}", "source_ref": "prompt"} for r in reqs],
    }


def _module(name: str, covers: list[str], deps: list[str] | None = None, files: list[str] | None = None, interfaces: bool = True) -> dict[str, Any]:
    return {
        "name": name, "goal": f"implement {name}", "files": files if files is not None else [f"src/{name}.py"], "deps": deps or [],
        "covers": covers, "acceptance": [f"{name} works"],
        "interfaces": [{"name": f"{name}_op", "signature": f"{name}_op() -> None", "returns": "None"}] if interfaces else [],
    }


GOOD_PLAN = {"modules": [_module("ledger", ["REQ-1"]), _module("billing", ["REQ-2"], deps=["ledger"])], "shared_types": [_module("types", [], interfaces=False)]}


class _Gateway:
    def __init__(self, *plans: dict[str, Any], t3_down: bool = False) -> None:
        self.plans = list(plans)
        self.t3_down = t3_down
        self.calls: list[tuple[str, str]] = []
        self.prompts: list[str] = []

    def model_for(self, role: Any, purpose: str, output_schema: Any = None, task_id: Any = None) -> Any:
        self.calls.append((role, purpose))
        if role == "T3" and self.t3_down:
            raise ProviderUnavailable("down")
        outer = self

        class _Model:
            def invoke(self, prompt: str) -> Any:
                outer.prompts.append(prompt)
                if purpose == "plan_critique":
                    return SimpleNamespace(content="NO_ISSUES")
                return outer.plans.pop(0) if len(outer.plans) > 1 else outer.plans[0]

        return _Model()


class _Broker:
    def __init__(self) -> None:
        self.requests: list[Any] = []

    def request(self, req: Any) -> None:
        self.requests.append(req)


class _Registry:
    def __init__(self) -> None:
        self.registered: list[Any] = []

    def register(self, spec: Any) -> Any:
        self.registered.append(spec)
        return spec


def _run(gateway: _Gateway, request: dict[str, Any], thread: str, **deps: Any) -> tuple[Any, dict[str, Any], Any]:
    graph = build_planner_graph(MemorySaver())
    config: Any = {"configurable": {"thread_id": thread, "gateway": gateway, "planner_strategy": "single_pass", **deps}}
    out = graph.invoke({"request": request, "run_id": "run1"}, config)
    return graph, out, config


def test_a_design_plan_waits_for_approval_then_emits_root_modules_and_contracts() -> None:
    broker, registry = _Broker(), _Registry()
    graph, paused, config = _run(_Gateway(GOOD_PLAN), _request(), "t-approve", decision_broker=broker, registry=registry)
    assert "__interrupt__" in paused
    (req,) = broker.requests
    assert req.kind.value == "approve_plan" and req.options == ["approve", "reject"]
    assert registry.registered == []  # nothing is registered before approval

    done = graph.invoke(Command(resume="approve"), config)
    plan = plan_result(done)
    assert plan is not None
    assert plan.run_id == "run1" and plan.root.id == "run1-root" and plan.root.kind.value == "composite"
    by_name = {str(n.id): n for n in plan.module_nodes}
    assert set(by_name) == {"run1-ledger", "run1-billing"}
    assert by_name["run1-billing"].deps == ["run1-ledger", "run1-types"]  # declared dependency plus the shared-types leaf (A-2)
    assert by_name["run1-billing"].allowed_files == ["src/billing.py"] and by_name["run1-billing"].contract_refs == ["billing@0.1.0"]
    assert [n.id for n in plan.shared_type_nodes] == ["run1-types"] and plan.shared_type_nodes[0].kind.value == "shared_types"
    assert plan.contract_ids == ["c-run1-ledger", "c-run1-billing"]
    assert [s.status.value for s in registry.registered] == ["DRAFT", "DRAFT"]
    assert all(n.parent_id == "run1-root" for n in plan.module_nodes)


def test_a_rejected_plan_produces_nothing() -> None:
    graph, paused, config = _run(_Gateway(GOOD_PLAN), _request(), "t-reject", decision_broker=_Broker(), registry=_Registry())
    done = graph.invoke(Command(resume="reject"), config)
    assert plan_result(done) is None and "rejected" in done["note"]


def test_a_small_clean_change_needs_no_approval() -> None:
    plan = {"modules": [_module("ledger", ["REQ-1", "REQ-2"])]}
    _, out, _ = _run(_Gateway(plan), _request("feature"), "t-impact")
    assert plan_result(out) is not None


def test_failed_checks_send_the_plan_back_and_the_failures_reach_the_prompt() -> None:
    bad = {"modules": [_module("ledger", ["REQ-1"])]}  # REQ-2 uncovered
    gateway = _Gateway(bad, GOOD_PLAN)
    _, paused, _ = _run(gateway, _request(), "t-revise", decision_broker=_Broker())
    assert "requirement REQ-2 is not covered" in gateway.prompts[1]
    assert "__interrupt__" in paused
    assert paused.get("problems") in (None, [])


def test_a_plan_that_never_passes_is_shown_to_the_user_with_its_failed_checks() -> None:
    bad = {"modules": [_module("ledger", ["REQ-1"])]}
    gateway, broker = _Gateway(bad), _Broker()
    _, paused, _ = _run(gateway, _request("feature"), "t-stubborn", decision_broker=broker)
    assert len([c for c in gateway.calls if c[1] == "plan"]) == 3  # the first plan plus two revisions
    assert "__interrupt__" in paused  # even a small change needs approval when checks still fail
    assert "REQ-2" in broker.requests[0].question


def test_an_unreachable_planning_tier_degrades_to_the_local_planner_with_mandatory_approval() -> None:
    gateway, broker = _Gateway({"modules": [_module("ledger", ["REQ-1", "REQ-2"])]}, t3_down=True), _Broker()
    _, paused, _ = _run(gateway, _request("feature"), "t-degraded", decision_broker=broker)
    assert [c[0] for c in gateway.calls if c[1] == "plan"] == ["T3", "T2"]
    assert "__interrupt__" in paused and "degraded" in broker.requests[0].question


def test_required_approval_without_a_broker_is_an_error() -> None:
    with pytest.raises(Exception) as info:  # noqa: PT011 - ApprovalRequired lives in contracts
        _run(_Gateway(GOOD_PLAN), _request(), "t-nobroker")
    assert type(info.value).__name__ == "ApprovalRequired"


def test_a_missing_gateway_is_reported_clearly() -> None:
    graph = build_planner_graph(None)
    with pytest.raises(RuntimeError, match="gateway"):
        graph.invoke({"request": _request(), "run_id": "r"}, {"configurable": {}})


def _check(plan: dict[str, Any], reqs: tuple[str, ...] = ("REQ-1",)) -> list[str]:
    return check_plan(PlanModel.model_validate(plan), StructuredRequest.model_validate(_request(reqs=reqs)))


def test_check_plan_accepts_a_good_plan() -> None:
    assert _check({"modules": [_module("a", ["REQ-1"]), _module("b", [], deps=["a"])]}) == []


def test_check_plan_finds_each_class_of_defect() -> None:
    assert any("no modules" in p for p in _check({"modules": []}))
    assert any("used twice" in p for p in _check({"modules": [_module("a", ["REQ-1"]), _module("a", [])]}))
    assert any("nobody produces" in p for p in _check({"modules": [_module("a", ["REQ-1"], deps=["ghost"])]}))
    assert any("owns no files" in p for p in _check({"modules": [_module("a", ["REQ-1"], files=[])]}))
    cyc = _check({"modules": [_module("a", ["REQ-1"], deps=["b"]), _module("b", [], deps=["a"])]})
    assert any("cycle among: a, b" in p for p in cyc)


def test_a_requirement_mentioned_in_acceptance_text_counts_as_covered() -> None:
    plan = {"modules": [{**_module("a", []), "acceptance": ["satisfies REQ-1 end to end"]}]}
    assert _check(plan) == []
