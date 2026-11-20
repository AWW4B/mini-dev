<!--
FILE: docs/FIRST_REAL_RUN.md
ROLE: Findings from the first real run of the factory on a small project: what broke, what was fixed and what is still open.
ARCH REF: M1-M5; docs/EXECUTION_PLAN.md
OWNS: The findings list of the first real run
DOES NOT OWN: Code, the execution plan
CONNECTS TO (external boundaries only):
  - imports from none: none
  - emits/consumes: none
INSTRUCTIONS (strict, imperative):
  1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
  2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
  3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
  4. Open text files with encoding="utf-8" explicitly.
FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
DONE WHEN: (1) `uv run python scripts/check_headers.py` reports no problem for this file.
-->

# First real runs: findings, the trace logger and the dummy profile

## How to see everything a run did
- Every run writes `<project>/.factory/logs/trace.jsonl` (machine readable) and `trace.log` (readable): one line per event with the
  component, the event, the **file:line and function that produced it**, the run, the task, the thread and a data payload.
- It records: model routes and every model call (role, provider, model, purpose, tokens in/out, latency, cost, prompt tail, reply, and the
  **limits used so far**: remote tokens, local tokens, API spend against their caps), every state commit, every tool call with its
  arguments and output, scheduler task states and attempts, worker turns, memory reads and writes, decisions asked and answered,
  decomposition sizing and splits, planner critiques, the run's narrative lines and every library log record with its traceback.
- `FACTORY_TRACE=calls` also records every function call and its duration inside the asf package (large; for hunting a hang);
  `FACTORY_TRACE=off` disables it.
- Model calls are also stored in `call_metrics` (`factory stats`), attributed to their task and labelled with their purpose.

## Running the whole flow without a model
`factory run start --file SPEC.md --mode new_build --profile dummy` uses a deterministic stand-in model for every role (no network, no
key, no cost): a planner that builds modules from the files the requirements name, a rubric, test authoring, a worker that writes files
and runs the tests, a classifier and a reviewer. It exists to fix the flow; real models then only change quality.

## Fixed (each on its own branch, merged to local main, with a test)
Intake and planning: attachments read back from blobs; the tiny model's rewrite is trusted only if it keeps every code token; `--mode`
wins over the keyword guess; requirement ids travel with each module's criteria and the test author is told to cite them (final
acceptance looks for each id in the tests); the contract registry is created, so planned signatures reach workers as capsules.
Decomposition: a tiny model's rubric can only nudge a heuristic score; answers to the decomposer's questions (accept a larger leaf,
clarified, abandon) are applied.
Worker and gate: the acceptance test source is in the prompt; `done` is refused until tests ran; a tool name in `action` is read as that
tool call; the local coder may run tests and the linter (the prompt offered them and the registry denied them); bytecode and caches are not
changes; a leaf that depends on others starts with their verified code merged in; mypy ignores imports it cannot resolve and ruff checks
for real errors only when the project has no ruff config; free VRAM is only required when the runtime loads the model itself.
Gateway and keys: several keys per provider with ordered fallbacks; strict json_schema refusals fall back to tool calling; a 429 moves to
the next key; remote calls time out after 60 s; one budget per run; the run remembers its profile and resume uses it.
Resume and state: queued leaf specs are saved when queued and re-queued by the resuming process; model-call metrics are queued and written
by the run's own connection (a second connection broke the main one with "database is locked"); the trace does not re-enter when
redaction logs (that hung the process).
Console: output is UTF-8 (a non-breaking hyphen crashed `tasks show`).

## Open
- A real model's quality (a 7B coder through the JSON tool protocol is weak): now the only remaining variable once the flow is fixed.
- The first call to each provider took 15-70 s (cause not found; possibly IPv6 fallback).
- Both llama-servers write one shared `llama-server.log`.
- The planner's opening narrative events appear twice after a resume (the node re-runs).
- The run process exits at the first human decision; unattended runs need a driver that answers decisions (a scratch script was used).
