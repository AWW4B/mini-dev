# FILE: tests/m3_orchestration/test_e2e.py
# ROLE: End-to-end test: a request goes through planning, decomposition, scheduling, the worker, the gate and integration on a real git repository.
# ARCH REF: M1-M5; D-35 (markers, fakes)
# OWNS: The whole-pipeline test with a scripted model
# DOES NOT OWN: Unit behaviour (each module has its own tests)
# CONNECTS TO (external boundaries only):
#   - called by tests/conftest.py: fake_paths
#   - imports from src/asf/m3_orchestration/run_graph.py: start_run (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
#   - imports from src/asf/contracts/requests.py: StructuredRequest (request fixture)
#   - imports from src/asf/m5_shared/state_store/store.py: StateStore (the run's real database)
#   - imports from src/asf/m5_shared/workspace/blobs.py: BlobStore (the delivered report)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m3_orchestration/test_e2e.py` on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m3_orchestration/test_e2e.py` and `uv run mypy tests/m3_orchestration/test_e2e.py` are clean.

import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from asf.contracts.requests import StructuredRequest
from asf.m3_orchestration.run_graph import start_run
from asf.m5_shared.state_store.store import StateStore
from asf.m5_shared.workspace.blobs import BlobStore

GREET = "def greet(name: str) -> str:\n    return f\"Hello, {name}!\"\n"
ACCEPTANCE = "# REQ-1: greeting\nfrom src.greet import greet\n\n\ndef test_greet() -> None:\n    assert greet(\"Ada\") == \"Hello, Ada!\"\n"


class _Gateway:
    """A scripted model for every tier: planner, rubric, acceptance-test author and coding worker."""

    def __init__(self, worker_content: str = GREET) -> None:
        self.worker_content = worker_content
        self.purposes: list[str] = []

    def model_for(self, role: Any, purpose: str, output_schema: Any = None, task_id: Any = None) -> Any:
        self.purposes.append(purpose)
        outer = self

        class _Model:
            def invoke(self, prompt: str) -> Any:
                if purpose == "plan":
                    return {
                        "modules": [
                            {
                                "name": "greet", "goal": "implement greet(name) that returns a greeting", "files": ["src/greet.py"], "covers": ["REQ-1"],
                                "acceptance": ["greet returns a greeting"], "interfaces": [{"name": "greet", "signature": "greet(name: str) -> str", "returns": "str"}],
                            }
                        ]
                    }
                if purpose == "rubric":
                    return {"ambiguity": 0.1, "coupling": 0.1, "notes": "scripted"}
                if purpose == "acceptance_tests":
                    return {"files": {"tests/test_greet.py": ACCEPTANCE}}
                if "Result:" not in prompt:
                    return SimpleNamespace(content=json.dumps({"action": "tool", "tool": "write_file", "args": {"rel_path": "src/greet.py", "content": outer.worker_content}}))
                return SimpleNamespace(content=json.dumps({"action": "done", "message": "implemented greet"}))

        return _Model()


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()  # noqa: S603, S607


def _local_runner(argv: list[str], cwd: Path, timeout_s: int) -> Any:
    """Runs a gate command with this interpreter instead of `uv run`, so the test needs no sandbox and no network."""
    command = [sys.executable, "-m", *argv[2:]] if argv[:2] == ["uv", "run"] else argv
    started = time.monotonic()
    done = subprocess.run(command, cwd=cwd, capture_output=True, timeout=timeout_s, check=False)  # noqa: S603
    return SimpleNamespace(exit_code=done.returncode, stdout=done.stdout, stderr=done.stderr, timed_out=False, duration_ms=int((time.monotonic() - started) * 1000))


def _regression(root: Path, selectors: list[str]) -> tuple[int, str]:
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header", *selectors], cwd=root, capture_output=True, text=True, check=False)  # noqa: S603
    return done.returncode, done.stdout + done.stderr


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".factory").mkdir(parents=True)
    (repo / ".factory" / ".gitignore").write_text("*\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".worktrees/\n.asf_blobs/\n.asf_locks/\n.factory/\n__pycache__/\n.pytest_cache/\n.mypy_cache/\n.ruff_cache/\n", encoding="utf-8")
    (repo / "README.md").write_text("demo\n", encoding="utf-8")
    _git(repo, "init")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    return repo


def _request() -> StructuredRequest:
    return StructuredRequest.model_validate(
        {
            "request_id": "q1", "project_id": "demo", "task_type": "feature",
            "requirements": [{"req_id": "REQ-1", "text": "greet a person by name", "source_ref": "prompt"}],
        }
    )


def _run(tmp_path: Path, gateway: _Gateway) -> tuple[Path, StateStore, dict[str, Any]]:
    repo = _repo(tmp_path)
    store = StateStore.open(repo / ".factory" / "state.db")
    over: dict[str, Any] = {
        "run_id": "run1", "state_store": store, "gateway": gateway, "profile": SimpleNamespace(c_eff_tokens=10_000),
        "blobs": BlobStore(tmp_path / "blobs"), "checkpointer": MemorySaver(), "planner_strategy": "single_pass",
        "sleep": lambda seconds: time.sleep(0.02), "gate_runner": _local_runner, "test_runner": _local_runner, "regression": _regression, "max_ticks": 3000,
    }
    start_run(_request(), repo, over)
    return repo, store, over


def _status(store: StateStore) -> str:
    return str(store.conn.execute("SELECT status FROM runs WHERE run_id = 'run1'").fetchone()["status"])


def _kinds(store: StateStore) -> list[str]:
    return [str(r["kind"]) for r in store.conn.execute("SELECT kind FROM events WHERE run_id = 'run1' ORDER BY seq")]


def test_a_request_becomes_tested_merged_code_through_the_real_worker_gate_scheduler_and_integrator(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    gateway = _Gateway()
    repo, store, over = _run(tmp_path, gateway)

    assert _status(store) == "DONE"
    assert (repo / "src" / "greet.py").read_text(encoding="utf-8") == GREET  # the worker's change was verified and merged
    assert (repo / "tests" / "test_greet.py").read_text(encoding="utf-8") == ACCEPTANCE  # the planner tier wrote the tests
    log = _git(repo, "log", "--format=%s")
    assert "acceptance tests for run1-greet" in log and "Merge task/run1-greet" in log and "task run1-greet attempt 1" in _git(repo, "log", "--all", "--format=%s")
    states = {r["task_id"]: r["state"] for r in store.conn.execute("SELECT task_id, state FROM tasks")}
    assert states == {"run1-root": "INTEGRATED", "run1-greet": "VERIFIED"}
    assert gateway.purposes.count("acceptance_tests") == 1 and "code_step" in gateway.purposes
    assert _regression(repo, [])[0] == 0  # the merged project passes its own tests
    _ = over


def test_the_event_log_tells_the_story_and_the_report_is_delivered(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    repo, store, _ = _run(tmp_path, _Gateway())
    kinds = _kinds(store)
    assert kinds[0] == "run_started" and kinds[-1] == "run_completed" and "gate_result" in kinds and "state_changed" in kinds
    done = [json.loads(r["payload"]) for r in store.conn.execute("SELECT payload FROM events WHERE kind = 'run_completed'")][0]
    report = BlobStore(tmp_path / "blobs").get(done["payload"]["report_ref"]).decode()
    assert "REQ-1: greet a person by name" in report and "Acceptance: passed" in report and "Nothing was deployed" in report
    _ = repo


def test_a_worker_that_writes_a_wrong_implementation_is_rejected_by_the_gate_and_never_merged(tmp_path: Path, fake_paths: Any) -> None:
    _ = fake_paths
    wrong = "def greet(name: str) -> str:\n    return \"Hi\"\n"
    repo, store, _ = _run(tmp_path, _Gateway(worker_content=wrong))
    assert _status(store) in ("FAILED", "WAITING", "RUNNING", "AWAITING_DECISION")  # it never reaches DONE
    assert not (repo / "src" / "greet.py").exists()  # nothing unverified landed on the integration branch
    assert "Hi" not in _git(repo, "log", "-p", "--format=%s")
