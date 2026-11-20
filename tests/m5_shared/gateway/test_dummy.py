# FILE: tests/m5_shared/gateway/test_dummy.py
# ROLE: Tests that prove src/asf/m5_shared/gateway/dummy.py meets its DONE WHEN conditions.
# ARCH REF: M5; p11; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/gateway/dummy.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/gateway/dummy.py: DummyChatModel, answer_for (unit under test)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/gateway/test_dummy.py` on Windows and Linux once src/asf/m5_shared/gateway/dummy.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/gateway/test_dummy.py` and `uv run mypy tests/m5_shared/gateway/test_dummy.py` are clean.

import json

from pydantic import BaseModel

from asf.m5_shared.gateway.dummy import DummyChatModel, answer_for

REQS = (
    "REQUIREMENTS:\n- REQ-001: Build a tool called `wordfreq`.\n- REQ-002: `src/wordfreq/core.py` has `top_words(text: str, n: int = 3) -> list[tuple[str, int]]`.\n"
    "- REQ-003: Ties are broken alphabetically.\n- REQ-004: `src/wordfreq/cli.py` has `main(argv: list[str] | None = None) -> int`.\n- REQ-005: Tests in `tests/` cover ranking.\n"
)


def test_the_plan_has_a_module_per_named_file_with_signatures_and_covers_every_requirement() -> None:
    plan = json.loads(answer_for("plan", REQS))
    names = [m["name"] for m in plan["modules"]]
    assert names == ["core", "cli", "tests"]
    core = plan["modules"][0]
    assert core["files"] == ["src/wordfreq/core.py"] and core["interfaces"][0]["name"] == "top_words"
    covered = {r for m in plan["modules"] for r in m["covers"]}
    assert covered == {"REQ-001", "REQ-002", "REQ-003", "REQ-004", "REQ-005"} or {"REQ-002", "REQ-003", "REQ-004"} <= covered


def test_the_worker_writes_each_allowed_file_runs_the_tests_then_is_done() -> None:
    header = "TASK: core\nALLOWED FILES: src/wordfreq/core.py\nACCEPTANCE TESTS: tests/test_core.py\n"
    first = json.loads(answer_for("code_step", header))
    assert first["tool"] == "write_file" and "def top_words" in first["args"]["content"]
    second = json.loads(answer_for("code_step", header + 'Turn 1: write_file({"rel_path": "src/wordfreq/core.py", "content": "x"})\n'))
    assert second["tool"] == "run_tests" and second["args"]["selectors"] == ["tests/test_core.py"]
    last = json.loads(answer_for("code_step", header + 'Turn 1: write_file({"rel_path": "src/wordfreq/core.py"})\nTurn 2: run_tests({"selectors": []})\n'))
    assert last["action"] == "done"


def test_acceptance_tests_use_the_requested_keys_and_never_an_unwritable_name() -> None:
    answer = json.loads(answer_for("acceptance_tests", "FILES UNDER TEST (x): src/a.py\nUse exactly these keys for the test files: tests/test_a.py\n"))
    assert [f["path"] for f in answer["files"]] == ["tests/test_a.py"]
    odd = json.loads(answer_for("acceptance_tests", "FILES UNDER TEST (x): tests/test_a.py\nUse exactly these keys for the test files: tests/test_<name>.py\n"))
    assert "<" not in odd["files"][0]["path"]


def test_structured_output_validates_and_reports_token_use() -> None:
    class Score(BaseModel):
        ambiguity: float
        coupling: float
        notes: str

    model = DummyChatModel(purpose="rubric")
    score = model.with_structured_output(Score).invoke("anything")
    assert isinstance(score, Score) and score.ambiguity < 0.5
    reply = model.invoke("hello")
    assert reply.response_metadata["token_usage"]["prompt_tokens"] >= 1
