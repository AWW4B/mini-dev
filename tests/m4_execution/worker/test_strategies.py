# FILE: tests/m4_execution/worker/test_strategies.py
# ROLE: Tests that prove src/asf/m4_execution/worker/strategies.py meets its DONE WHEN conditions.
# ARCH REF: M4; p07; D-09 worker strategies; D-19; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m4_execution/worker/strategies.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m4_execution/worker/strategies.py: run_strategy, WorkerStrategyName, WorkerBlocked, WorkerFormatError (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m4_execution/worker/test_strategies.py` on Windows and Linux once src/asf/m4_execution/worker/strategies.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m4_execution/worker/test_strategies.py` and `uv run mypy tests/m4_execution/worker/test_strategies.py` are clean.

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from asf.m4_execution.worker.strategies import WorkerBlocked, WorkerFormatError, WorkerStrategyName, run_strategy


class _Gateway:
    """Replays scripted model replies and records every prompt."""

    def __init__(self, *replies: Any) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    def model_for(self, role: Any, purpose: str, **_: Any) -> Any:
        outer = self

        class _Model:
            def invoke(self, prompt: str) -> Any:
                outer.prompts.append(prompt)
                reply = outer.replies.pop(0)
                if isinstance(reply, Exception):
                    raise reply
                return SimpleNamespace(content=reply if isinstance(reply, str) else json.dumps(reply))

        return _Model()


class _Executor:
    def __init__(self, tier: str = "A", ok: bool = True) -> None:
        self.tier = tier
        self.ok = ok
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def active_tier(self) -> str:
        return self.tier

    def invoke(self, invocation: Any, allowed_files: list[str]) -> Any:
        self.calls.append((invocation.tool, invocation.args))
        return SimpleNamespace(status="ok" if self.ok else "denied", output="file contents" if self.ok else "outside allowed files")


def _spec(max_turns: int = 4, wall_clock_s: int = 60, tests: tuple[str, ...] = ()) -> Any:
    return SimpleNamespace(
        task_id="t1",
        goal="write src/billing.py",
        allowed_files=["src/billing.py"],
        read_only_files=[],
        acceptance_test_refs=list(tests),
        capsules=[SimpleNamespace(module_id="ledger", operation="record", lines=["record(entry) -> None", "raises LedgerError", "idempotent"])],
        step_budget=SimpleNamespace(max_turns=max_turns, wall_clock_s=wall_clock_s),
        context_budget_tokens=8192,
    )


def _run(name: WorkerStrategyName, gateway: _Gateway, executor: _Executor, tmp_path: Path, spec: Any = None) -> str:
    return run_strategy(name, spec or _spec(), str(tmp_path), gateway=gateway, executor=executor, context="CTX")  # type: ignore[arg-type]


def test_tool_loop_calls_tools_until_the_model_says_done(tmp_path: Path) -> None:
    gateway = _Gateway(
        {"action": "tool", "tool": "read_file", "args": {"rel_path": "src/billing.py"}},
        {"action": "tool", "tool": "write_file", "args": {"rel_path": "src/billing.py", "content": "x = 1"}},
        {"action": "done", "message": "implemented"},
    )
    executor = _Executor()
    report = _run("tool_loop", gateway, executor, tmp_path)
    assert "3 step(s)" in report and "implemented" in report
    assert [c[0] for c in executor.calls] == ["read_file", "write_file"]
    assert "file contents" in gateway.prompts[1]  # the observation is fed back
    assert "ledger.record" in gateway.prompts[0] and "CTX" in gateway.prompts[0] and "src/billing.py" in gateway.prompts[0]


def test_a_malformed_reply_is_repaired_within_two_retries(tmp_path: Path) -> None:
    gateway = _Gateway("no json here", "still { not json", {"action": "done", "message": "ok"})
    assert "ok" in _run("tool_loop", gateway, _Executor(), tmp_path)
    assert "rejected" in gateway.prompts[1]


def test_three_malformed_replies_raise_a_format_error(tmp_path: Path) -> None:
    gateway = _Gateway("a", "b", "c")
    with pytest.raises(WorkerFormatError):
        _run("tool_loop", gateway, _Executor(), tmp_path)


def test_blocked_is_surfaced_to_the_orchestrator(tmp_path: Path) -> None:
    blocked = {"action": "blocked", "message": "CONTRACT_GAP: ledger has no refund operation"}
    gateway = _Gateway(blocked, blocked, blocked)  # a block before any write is pushed back twice
    with pytest.raises(WorkerBlocked) as info:
        _run("tool_loop", gateway, _Executor(), tmp_path)
    assert "CONTRACT_GAP" in str(info.value)


def test_the_turn_budget_is_enforced(tmp_path: Path) -> None:
    gateway = _Gateway(*[{"action": "tool", "tool": "search_code", "args": {"pattern": "charge"}}] * 3)
    with pytest.raises(WorkerBlocked) as info:
        _run("tool_loop", gateway, _Executor(), tmp_path, _spec(max_turns=3))
    assert "SPEC_TOO_LARGE" in str(info.value)
    assert len(gateway.prompts) == 3


def test_an_unknown_action_is_reported_back_and_costs_a_turn(tmp_path: Path) -> None:
    gateway = _Gateway({"action": "dance"}, {"action": "done", "message": "fine"})
    assert "fine" in _run("tool_loop", gateway, _Executor(), tmp_path)
    assert "invalid action" in gateway.prompts[1]


def test_whole_file_edit_writes_every_file_through_the_tool_executor(tmp_path: Path) -> None:
    gateway = _Gateway({"action": "done", "message": "rewrote it", "files": {"src/billing.py": "def charge(): ...\n"}})
    executor = _Executor()
    report = _run("whole_file_edit", gateway, executor, tmp_path)
    assert "1 file" in report
    assert executor.calls == [("write_file", {"rel_path": "src/billing.py", "content": "def charge(): ...\n"})]


def test_whole_file_edit_fails_when_the_executor_denies_the_write(tmp_path: Path) -> None:
    gateway = _Gateway({"action": "done", "message": "m", "files": {"src/other.py": "x"}})
    with pytest.raises(WorkerFormatError):
        _run("whole_file_edit", gateway, _Executor(ok=False), tmp_path)


def test_diff_edit_applies_a_unified_diff_to_an_allowed_file(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "billing.py").write_text("a = 1\n", encoding="utf-8")
    diff = "--- a/src/billing.py\n+++ b/src/billing.py\n@@ -1 +1,2 @@\n a = 1\n+b = 2\n"
    report = _run("diff_edit", _Gateway({"action": "done", "message": "added b", "diff": diff}), _Executor(), tmp_path)
    assert "1 file" in report
    assert (tmp_path / "src" / "billing.py").read_text(encoding="utf-8") == "a = 1\nb = 2\n"
    assert not (tmp_path / ".asf_worker.patch").exists()


def test_diff_edit_rejects_files_outside_the_allowed_set_before_applying(tmp_path: Path) -> None:
    (tmp_path / "other.py").write_text("a = 1\n", encoding="utf-8")
    diff = "--- a/other.py\n+++ b/other.py\n@@ -1 +1,2 @@\n a = 1\n+evil = 1\n"
    with pytest.raises(WorkerFormatError):
        _run("diff_edit", _Gateway({"action": "done", "message": "m", "diff": diff}), _Executor(), tmp_path)
    assert (tmp_path / "other.py").read_text(encoding="utf-8") == "a = 1\n"


def test_diff_edit_reports_a_diff_that_does_not_apply(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "billing.py").write_text("something else\n", encoding="utf-8")
    diff = "--- a/src/billing.py\n+++ b/src/billing.py\n@@ -1 +1,2 @@\n a = 1\n+b = 2\n"
    with pytest.raises(WorkerFormatError):
        _run("diff_edit", _Gateway({"action": "done", "message": "m", "diff": diff}), _Executor(), tmp_path)


@pytest.mark.parametrize("tier", ["B", "C"])
def test_code_exec_falls_back_to_the_tool_loop_without_a_tier_a_sandbox(tmp_path: Path, tier: str) -> None:
    gateway = _Gateway({"action": "done", "message": "via loop"})
    assert "tool_loop" in _run("code_exec", gateway, _Executor(tier=tier), tmp_path)


def test_an_unknown_strategy_is_a_programming_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _run("magic", _Gateway(), _Executor(), tmp_path)  # type: ignore[arg-type]


def test_a_tool_name_in_the_action_field_is_read_as_that_tool_call(tmp_path: Path) -> None:
    """Measured with the local 7B coder: {"action": "write_file", "rel_path": ..., "content": ...} cost every attempt its whole turn budget."""
    gateway = _Gateway(
        {"action": "write_file", "rel_path": "src/billing.py", "content": "def charge(): ...\n"},
        {"action": "write_file", "args": {"rel_path": "src/b2.py", "content": "x = 1\n"}},
        {"action": "done", "message": "wrote both"},
    )
    executor = _Executor()
    assert "wrote both" in _run("tool_loop", gateway, executor, tmp_path)
    assert executor.calls[:2] == [
        ("write_file", {"rel_path": "src/billing.py", "content": "def charge(): ...\n"}),
        ("write_file", {"rel_path": "src/b2.py", "content": "x = 1\n"}),
    ]
    assert "invalid action" not in gateway.prompts[1]


def test_done_is_refused_until_the_acceptance_tests_have_been_run(tmp_path: Path) -> None:
    """Measured: the 7B coder wrote count_word_frequency() where the tests import top_words(), said done after one write and never ran a test.
    Now the tests run by themselves after every write, so done is refused only while nothing was written and tested."""
    gateway = _Gateway(
        {"action": "done", "message": "too early"},
        {"action": "write_file", "rel_path": "src/billing.py", "content": "x = 1\n"},
        {"action": "done", "message": "tests pass"},
    )
    executor = _Executor()
    assert "tests pass" in _run("tool_loop", gateway, executor, tmp_path, _spec(max_turns=6, tests=("tests/test_billing.py",)))
    assert [name for name, _ in executor.calls] == ["write_file", "run_tests"]
    assert "done was refused" in gateway.prompts[1] and "ran by themselves after this write" in gateway.prompts[2]


def test_the_acceptance_test_source_is_in_front_of_the_worker(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_billing.py").write_text("from billing import top_words\n", encoding="utf-8")
    gateway = _Gateway({"action": "tool", "tool": "run_tests", "args": {}}, {"action": "done", "message": "ok"})
    _run("tool_loop", gateway, _Executor(), tmp_path, _spec(tests=("tests/test_billing.py",)))
    assert "ACCEPTANCE TEST SOURCE" in gateway.prompts[0] and "import top_words" in gateway.prompts[0]


def test_run_tests_with_test_function_names_runs_the_tasks_own_test_files(tmp_path: Path) -> None:
    """The 7B coder passed ['test_top_words_basic'] (names, not files): pytest exit 4, 'the tests cannot be found', task blocked."""
    gateway = _Gateway(
        {"action": "tool", "tool": "run_tests", "args": {"selectors": ["test_top_words_basic", "test_ties"]}},
        {"action": "tool", "tool": "run_tests", "args": {"selectors": ["tests/test_other.py"]}},
        {"action": "done", "message": "ok"},
    )
    executor = _Executor()
    _run("tool_loop", gateway, executor, tmp_path, _spec(max_turns=5, tests=("tests/test_billing.py",)))
    assert [args["selectors"] for name, args in executor.calls if name == "run_tests"] == [["tests/test_billing.py"], ["tests/test_other.py"]]


def test_a_first_blocked_before_any_write_is_pushed_back_once(tmp_path: Path) -> None:
    """The 7B coder answered blocked at turn 1 ('the code for core.py is not provided') for a task about cli.py; one push-back made it write."""
    gateway = _Gateway(
        {"action": "blocked", "message": "the code for another module is missing"},
        {"action": "tool", "tool": "write_file", "args": {"rel_path": "src/billing.py", "content": "x = 1\n"}},
        {"action": "done", "message": "wrote it"},
    )
    assert "wrote it" in _run("tool_loop", gateway, _Executor(), tmp_path)
    assert "blocked was refused" in gateway.prompts[1]


def test_a_block_that_survives_the_push_backs_is_a_real_block(tmp_path: Path) -> None:
    gateway = _Gateway({"action": "blocked", "message": "gap one"}, {"action": "blocked", "message": "gap two"}, {"action": "blocked", "message": "CONTRACT_GAP: ledger has no refund operation"})
    with pytest.raises(WorkerBlocked) as info:
        _run("tool_loop", gateway, _Executor(), tmp_path)
    assert "CONTRACT_GAP" in str(info.value)


def test_blocked_after_a_failing_test_run_is_pushed_back_to_fix_the_code(tmp_path: Path) -> None:
    """The 7B coder wrote the code, saw one failing test and answered blocked instead of fixing it."""

    class _Failing(_Executor):
        def invoke(self, invocation: Any, allowed_files: list[str]) -> Any:
            result = super().invoke(invocation, allowed_files)
            if invocation.tool == "run_tests":
                return SimpleNamespace(status="ok", output="(1, 'FAILED tests/test_billing.py::test_a')")
            return result

    gateway = _Gateway(
        {"action": "tool", "tool": "write_file", "args": {"rel_path": "src/billing.py", "content": "x = 1\n"}},
        {"action": "tool", "tool": "run_tests", "args": {"selectors": ["tests/test_billing.py"]}},
        {"action": "blocked", "message": "the test failed"},
        {"action": "tool", "tool": "write_file", "args": {"rel_path": "src/billing.py", "content": "x = 2\n"}},
        {"action": "done", "message": "fixed"},
    )
    assert "fixed" in _run("tool_loop", gateway, _Failing(), tmp_path, _spec(max_turns=8, tests=("tests/test_billing.py",)))
    assert "the acceptance tests failed. Failure output:" in gateway.prompts[3] and "FAILED tests/test_billing.py::test_a" in gateway.prompts[3]


def test_the_source_of_modules_already_in_the_worktree_is_shown_to_the_worker(tmp_path: Path) -> None:
    """The cli task answered 'core.py does not exist' on turn 1 although its dependency had been merged in."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "dep.py").write_text("def top_words(text):\n    return []\n", encoding="utf-8")
    gateway = _Gateway({"action": "done", "message": "ok"})
    _run("tool_loop", gateway, _Executor(), tmp_path, _spec(max_turns=3))
    assert "EXISTING CODE" in gateway.prompts[0] and "def top_words(text)" in gateway.prompts[0]


def test_a_write_whose_content_has_raw_double_quotes_is_still_written(tmp_path: Path) -> None:
    """The 7B coder put print(f"Error: ...") unescaped inside the JSON string; the re-ask made it answer 'blocked: invalid escape'."""
    reply = '```json\n{\n  "action": "write_file",\n  "rel_path": "src/billing.py",\n  "content": "import sys\n\ndef f():\n    print(f"Error: {sys.argv}")\n    return 1\n"\n}\n```'
    gateway = _Gateway(reply, {"action": "done", "message": "ok"})
    executor = _Executor()
    _run("tool_loop", gateway, executor, tmp_path, _spec(max_turns=4))
    name, args = next(call for call in executor.calls if call[0] == "write_file")
    assert args["rel_path"] == "src/billing.py"
    assert args["content"] == 'import sys\n\ndef f():\n    print(f"Error: {sys.argv}")\n    return 1\n'


def test_a_later_step_of_one_file_sees_the_earlier_work_marked_as_its_own(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "billing.py").write_text("def first():\n    return 1\n", encoding="utf-8")
    gateway = _Gateway({"action": "done", "message": "ok"})
    _run("tool_loop", gateway, _Executor(), tmp_path, _spec(max_turns=3))
    assert "src/billing.py (YOURS" in gateway.prompts[0] and "def first()" in gateway.prompts[0]


def test_a_helper_attempt_asks_the_bigger_tier_while_tools_stay_the_workers(tmp_path: Path) -> None:
    roles: list[str] = []

    class _Roles(_Gateway):
        def model_for(self, role: Any, purpose: str, **kw: Any) -> Any:
            roles.append(str(role))
            return super().model_for(role, purpose, **kw)

    gateway = _Roles({"action": "done", "message": "ok"})
    spec = _spec(max_turns=2)
    run_strategy("tool_loop", spec, str(tmp_path), gateway=gateway, executor=_Executor(), model_role="T3")  # type: ignore[arg-type]
    assert roles == ["T3"]


def test_a_salvaged_write_does_not_keep_the_json_tail_in_the_file(tmp_path: Path) -> None:
    """A real run left '\"}' as the last line of cli.py and every test then failed on a SyntaxError."""
    tail = chr(34) + "}"
    reply = '{"action": "write_file", "rel_path": "src/billing.py", "content": "def f():\n    print(f"E: {1}")\n' + tail + "\n" + tail
    gateway = _Gateway(reply, {"action": "done", "message": "ok"})
    executor = _Executor()
    _run("tool_loop", gateway, executor, tmp_path, _spec(max_turns=4))
    args = next(call[1] for call in executor.calls if call[0] == "write_file")
    assert args["content"].endswith("\n") and not args["content"].rstrip().endswith("}") and "def f():" in args["content"]


def test_a_file_in_a_fenced_block_after_the_json_is_written_verbatim(tmp_path: Path) -> None:
    """The coder writes the file after the JSON in a fence (aider's whole format): no escaping, so quotes and backslashes survive."""
    fence = chr(96) * 3
    body = 'import re\n\ndef f():\n    print(f"E: {re.escape(chr(92))}")\n'
    reply = fence + 'json\n{"action": "tool", "tool": "write_file", "args": {"rel_path": "src/billing.py"}}\n' + fence + "\n" + fence + "python\n" + body + fence
    gateway = _Gateway(reply, {"action": "done", "message": "ok"})
    executor = _Executor()
    _run("tool_loop", gateway, executor, tmp_path, _spec(max_turns=4))
    args = next(call[1] for call in executor.calls if call[0] == "write_file")
    assert args == {"rel_path": "src/billing.py", "content": body}


def test_a_block_after_writing_but_before_any_test_run_is_refused(tmp_path: Path) -> None:
    """Run 6: the 7B wrote core.py without `import re`, then answered blocked claiming `re` is not in the standard library."""

    class _NoTests(_Executor):
        def invoke(self, invocation: Any, allowed_files: list[str]) -> Any:
            if invocation.tool == "run_tests":
                return SimpleNamespace(status="ok", output="(1, 'NameError: re')")
            return super().invoke(invocation, allowed_files)

    gateway = _Gateway(
        {"action": "blocked", "message": "re is not available"},
        {"action": "write_file", "rel_path": "src/billing.py", "content": "import re\n"},
        {"action": "done", "message": "fixed"},
    )
    spec = _spec(max_turns=6)
    assert "fixed" in _run("tool_loop", gateway, _NoTests(), tmp_path, spec)
    assert "blocked was refused" in gateway.prompts[1]
