# FILE: src/asf/cli/commands/run.py
# ROLE: Implements `factory run start|status|pause|resume|abort|cancel-task`.
# ARCH REF: M1; p02 Project Input, Run Controls; IF-01; IF-05; D-09 overrides; D-10 switch; D-15
# OWNS: Argument parsing and output for this command group
# DOES NOT OWN: Business logic (lives in the imported modules)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m2_request/intake_router.py: submit (IF-01)
#   - imports from src/asf/m3_orchestration/run_graph.py: start_run, resume_run (run lifecycle)
#   - imports from src/asf/cli/project_input.py: build_submit_request (IF-01 payload)
#   - imports from src/asf/cli/run_controls.py: send_command (IF-05)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - imports from src/asf/cli/context.py: EXIT_ENV, EXIT_OK, EXIT_USER, default_output, guard, open_store, project_id_for, project_root, renderer_for, resolve_run_id (shared CLI plumbing)
#   - imports from src/asf/config/paths.py: get_paths (the log directory of detached runs)
#   - imports from src/asf/contracts/budget.py: RunBudget (the run budget)
#   - imports from src/asf/contracts/control.py: RunCommand (pause / abort / cancel-task)
#   - imports from src/asf/contracts/errors.py: ConfigError (bad ROLE=NAME pairs and gateway setup)
#   - imports from src/asf/contracts/requests.py: TaskType (the --mode option)
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (model routing for intake and the run)
#   - imports from src/asf/platform/select.py: get_platform (detached runs)
#   - called by src/asf/cli/flows.py: run_start, run_resume
#   - called by src/asf/cli/app.py: register
#   - called by tests/cli/commands/test_run.py: run_start, run_status, run_pause, run_resume, run_abort, run_cancel_task, register
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Never run agents or keep execution state in the CLI; write commands to the command table (IF-05) and read state/events (M1 is a thin client).
#   9. Support --output rich|plain|json through Renderer; prompts only when stdin and stdout are TTYs, otherwise exit 2 naming the missing flags (D-13).
#   10. Exit codes: 0 success, 1 user/validation error, 2 environment problem.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/cli/commands/test_run.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/commands/run.py` and `uv run mypy src/asf/cli/commands/run.py` are clean.

import sys
import time
from pathlib import Path
from typing import Any

import typer

from asf.cli.context import (
    EXIT_ENV,
    EXIT_OK,
    EXIT_USER,
    default_output,
    guard,
    open_store,
    project_id_for,
    project_root,
    renderer_for,
    resolve_run_id,
)
from asf.cli.project_input import build_submit_request
from asf.cli.run_controls import send_command
from asf.config.paths import get_paths
from asf.contracts.budget import RunBudget
from asf.contracts.control import RunCommand
from asf.contracts.errors import ConfigError
from asf.contracts.requests import TaskType
from asf.m2_request.intake_router import submit
from asf.m3_orchestration.run_graph import resume_run, start_run
from asf.m5_shared.gateway.gateway import ModelGateway
from asf.platform.select import get_platform

_WAITING = ("AWAITING_DECISION", "PAUSED")


def _pairs(values: list[str], flag: str) -> dict[str, str]:
    """--model ROLE=NAME and --strategy ROLE=NAME may repeat (D-09)."""
    result: dict[str, str] = {}
    for value in values:
        role, sep, name = value.partition("=")
        if not sep or not role.strip() or not name.strip():
            raise ConfigError(f"{flag} expects ROLE=NAME (for example T2=qwen2.5-coder), got '{value}'.")
        result[role.strip()] = name.strip()
    return result


def _budget(run_id: str) -> RunBudget:
    return RunBudget.model_validate(
        {"run_id": run_id, "max_remote_tokens": 2_000_000, "max_local_tokens": 20_000_000, "max_api_spend": 20.0, "max_wall_clock_s": 6 * 3600, "max_task_nodes": 500}
    )


def _gateway(profile: str, models: dict[str, str], strategies: dict[str, str]) -> ModelGateway:
    gateway = ModelGateway(profile, _budget("pending"))
    for role, name in models.items():
        gateway.roles.setdefault(role, {})["model"] = name
    gateway.strategies.update(strategies)
    return gateway


def _overrides(profile: str | None, model: list[str], strategy: list[str], local_tests: bool) -> dict[str, Any]:
    models, strategies = _pairs(model, "--model"), _pairs(strategy, "--strategy")
    try:
        gateway = _gateway(profile or "hybrid", models, strategies)
    except ConfigError:
        raise
    except Exception as err:  # noqa: BLE001 - provider construction raises many types; the fix is always the model setup
        raise ConfigError(f"The model gateway could not be set up ({err}). Run `factory models init` and `factory doctor`.") from err
    return {"gateway": gateway, "profile_name": profile or "hybrid", "model_overrides": models, "strategy_overrides": strategies, "allow_local_tests": local_tests}


def run_start(
    input_text: str | None,
    input_files: list[Path],
    repo: str | None,
    mode: str | None,
    profile: str | None,
    model: list[str],
    strategy: list[str],
    local_tests_with_approval: bool = False,
    detach: bool = False,
) -> int:
    """--model ROLE=NAME and --strategy ROLE=NAME may repeat (D-09)."""
    renderer = renderer_for(default_output())
    if not input_text and not input_files and not repo:
        renderer.message("Nothing to build: pass --input TEXT, --file PATH or --repo PATH_OR_URL (or run `factory` for the guided flow).", "error")
        return EXIT_ENV if not sys.stdin.isatty() else EXIT_USER
    try:
        hint = TaskType(mode) if mode else None
    except ValueError:
        renderer.message(f"Unknown mode '{mode}'. Use one of: {', '.join(t.value for t in TaskType if t is not TaskType.UNSUPPORTED)}.", "error")
        return EXIT_USER

    root = project_root()
    store = open_store(root=root)
    request = build_submit_request(project_id_for(root), input_text or "", input_files, repo, hint)
    if detach:
        argv = [sys.executable, "-m", "asf", "run", "start"]
        for flag, value in (("--input", input_text), ("--repo", repo), ("--mode", mode), ("--profile", profile)):
            if value:
                argv += [flag, value]
        for path in input_files:
            argv += ["--file", str(path)]
        for pair in model:
            argv += ["--model", pair]
        for pair in strategy:
            argv += ["--strategy", pair]
        if local_tests_with_approval:
            argv.append("--local-tests-with-approval")
        log = get_paths().log_dir / f"run-{int(time.time())}.log"
        pid = get_platform().detach(argv, log)
        renderer.message(f"The run continues in the background (process {pid}); log: {log}. Follow it with `factory trace --follow`.", "success")
        return EXIT_OK

    overrides = _overrides(profile, model, strategy, local_tests_with_approval)
    structured = submit(request, state_store=store, gateway=overrides["gateway"])
    run_id = start_run(structured, root, {**overrides, "state_store": store})
    return _report_state(renderer, run_id)


def _report_state(renderer: Any, run_id: str) -> int:
    store = open_store(readonly=True)
    try:
        row = store.conn.execute("SELECT status FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        pending = int(store.conn.execute("SELECT COUNT(*) FROM decisions WHERE run_id = ? AND status = 'PENDING'", (run_id,)).fetchone()[0])
    finally:
        store.close()
    status = str(row["status"]) if row is not None else "UNKNOWN"
    hints = {
        "DONE": "The report is ready: factory report " + run_id,
        "PAUSED": "Resume with: factory run resume " + run_id,
        "AWAITING_DECISION": "A decision is waiting: factory inbox list, then factory run resume " + run_id,
        "FAILED": "See what happened: factory trace " + run_id,
        "CANCELLED": "The run was cancelled.",
    }
    hint = hints.get(status, f"{pending} decision(s) waiting: factory inbox list" if pending else "Follow it with: factory trace --follow")
    renderer.record("Run", {"run id": run_id, "status": status, "next": hint})
    return EXIT_USER if status == "FAILED" else EXIT_OK


def run_status(run_id: str | None, output: str = "rich") -> int:
    renderer = renderer_for(output)
    store = open_store(readonly=True)
    try:
        chosen = resolve_run_id(store, run_id)
        run = store.conn.execute("SELECT project_id, status, cost, cost_estimated, last_activity FROM runs WHERE run_id = ?", (chosen,)).fetchone()
        if run is None:
            renderer.message(f"Unknown run '{chosen}'.", "error")
            return EXIT_USER
        states = {str(r["state"]): int(r["n"]) for r in store.conn.execute("SELECT state, COUNT(*) AS n FROM tasks WHERE run_id = ? GROUP BY state", (chosen,))}
        pending = int(store.conn.execute("SELECT COUNT(*) FROM decisions WHERE run_id = ? AND status = 'PENDING'", (chosen,)).fetchone()[0])
    finally:
        store.close()
    renderer.record(
        f"Run {chosen}",
        {
            "status": run["status"], "project": run["project_id"], "last activity": run["last_activity"],
            "cost": f"{run['cost']:.4f}{' EST' if run['cost_estimated'] else ''}",
            "tasks": ", ".join(f"{s}: {n}" for s, n in sorted(states.items())) or "none yet", "decisions waiting": pending,
        },
    )
    return EXIT_OK


def _send(run_id: str, command: RunCommand, task_id: str | None = None) -> int:
    command_id = send_command(run_id, command, task_id)
    renderer_for("plain").message(f"{command.value} sent ({command_id}); the run applies it at its next step.", "success")
    return EXIT_OK


def run_pause(run_id: str) -> int:
    return _send(run_id, RunCommand.PAUSE)


def run_abort(run_id: str) -> int:
    return _send(run_id, RunCommand.ABORT)


def run_cancel_task(run_id: str, task_id: str) -> int:
    return _send(run_id, RunCommand.CANCEL_TASK, task_id)


def run_resume(run_id: str) -> int:
    """Continue a paused run, or a run whose decision has been answered, from its checkpoint."""
    renderer = renderer_for(default_output())
    overrides = _overrides(None, [], [], False)
    store = open_store()
    resume_run(run_id, project_root(), {**overrides, "state_store": store})
    return _report_state(renderer, run_id)


def register(app: typer.Typer) -> None:
    """Attach the `run` command(s) to the root Typer app."""
    group = typer.Typer(help="Start and control runs.", no_args_is_help=True)

    @group.command("start")
    def start_cmd(
        input_text: str | None = typer.Option(None, "--input", "-i", help="The request as text"),
        input_files: list[Path] = typer.Option([], "--file", "-f", help="A requirements document (repeatable)"),
        repo: str | None = typer.Option(None, "--repo", help="Existing repository: local path or git URL"),
        mode: str | None = typer.Option(None, "--mode", help="new_build | debug | feature | refactor | test_generation | code_docs"),
        profile: str | None = typer.Option(None, "--profile", help="Model profile (local | api | hybrid)"),
        model: list[str] = typer.Option([], "--model", help="ROLE=NAME, repeatable"),
        strategy: list[str] = typer.Option([], "--strategy", help="ROLE=NAME, repeatable"),
        local_tests_with_approval: bool = typer.Option(False, "--local-tests-with-approval", help="Allow local drafts of acceptance tests if the planner tier is down (asks first)"),
        detach: bool = typer.Option(False, "--detach", help="Run in the background"),
    ) -> None:
        raise typer.Exit(code=guard(lambda: run_start(input_text, input_files, repo, mode, profile, model, strategy, local_tests_with_approval, detach)))

    @group.command("status")
    def status_cmd(run_id: str | None = typer.Argument(None), output: str = typer.Option("rich", "--output", "-o")) -> None:
        raise typer.Exit(code=guard(lambda: run_status(run_id, output)))

    @group.command("pause")
    def pause_cmd(run_id: str) -> None:
        raise typer.Exit(code=guard(lambda: run_pause(run_id)))

    @group.command("resume")
    def resume_cmd(run_id: str) -> None:
        raise typer.Exit(code=guard(lambda: run_resume(run_id)))

    @group.command("abort")
    def abort_cmd(run_id: str) -> None:
        raise typer.Exit(code=guard(lambda: run_abort(run_id)))

    @group.command("cancel-task")
    def cancel_task_cmd(run_id: str, task_id: str) -> None:
        raise typer.Exit(code=guard(lambda: run_cancel_task(run_id, task_id)))

    app.add_typer(group, name="run")
