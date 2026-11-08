<!--
FILE: docs/CONTINUATION.md
ROLE: Developer guide and continuation instructions for all batches and units of work across systems.
ARCH REF: M1-M5; all modules
OWNS: Continuation instructions and batch roadmap
DOES NOT OWN: Implementation code or individual file headers
CONNECTS TO (external boundaries only):
  - imports from none: none
  - emits/consumes: none
INSTRUCTIONS (strict, imperative):
  1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
  2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
  3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
  4. Open text files with encoding="utf-8" explicitly.
  5. Follow the batch roadmap and per-unit workflow to resume development on any machine.
FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
DONE WHEN: (1) `uv run python scripts/check_headers.py` reports no problem for this file.
-->

# AI Software Factory - Development & Continuation Guide

This document preserves the complete roadmap, ground rules, environment setup, and per-unit instructions so that work can be seamlessly resumed upon cloning to any system (Windows, Ubuntu/Debian, or Arch Linux).

---

## 1. Quick Setup on a New Machine

1. **Install Prerequisites**:
   - Python 3.12, 3.13, or 3.14
   - Git
   - [uv](https://docs.astral.sh/uv/) (Astral Python package manager)

2. **Clone & Sync**:
   ```bash
   git clone <repo_url>
   cd mini-dev
   uv sync --locked --extra web --extra anthropic --extra gemini
   ```
   *(Do not include `--extra docs-advanced` unless GPU torch/CUDA is available.)*

3. **Verify Baseline State**:
   ```bash
   uv run factory doctor
   uv run python scripts/check_headers.py --coverage
   uv run python scripts/scan_forbidden.py
   uv run pytest tests/config tests/platform tests/doctor tests/m5_shared/events tests/m5_shared/workspace tests/m5_shared/state_store tests/m5_shared/decisions tests/m5_shared/metrics -v
   ```

---

## 2. Ground Rules for Implementation (from AGENTS.md)

1. **Unit of Work**:
   ONE source file + its mirrored test file (`tests/<path>/test_<stem>.py`).
   Read **only** that target file's header and the files listed under its `CONNECTS TO`.
   Do not browse or modify unrelated files.

2. **Contract Preservation**:
   Never alter another file's code.
   Never alter headers, signatures, or public names.
   If a contract must change, stop and report to the user before proceeding.

3. **Cross-Platform Compatibility**:
   Must pass on Windows and Linux (Debian/Ubuntu and Arch).
   Use `pathlib.Path` everywhere.
   Retrieve base directories **only** via `src/asf/config/paths.py`.
   Subprocesses must be invoked using argument lists only (`shell=False`, no `os.system`).
   Route OS-specific actions (sandboxing, process tree management, file locking) through `asf.platform.select.get_platform()`.

4. **Security & Dependencies**:
   Never commit secrets, API keys, model weights, or run artifacts.
   Do not add or upgrade dependencies without explicit permission (exact pins in `pyproject.toml` and `uv.lock`).

---

## 3. Standard Per-Unit Workflow

For each unit:
1. **Read Header**: Read the target source file header and check `CONNECTS TO`.
2. **Write Tests**: Implement test cases in `tests/<path>/test_<stem>.py` satisfying all conditions in the target header.
   - Note: The test file itself has strict import constraints; it must only import modules declared in its own header's `CONNECTS TO` (plus pytest and stdlib). Use duck typing or fixtures from `tests/conftest.py`.
3. **Implement Source**: Implement the source file with minimal clean diffs.
4. **Run Verification Commands**:
   ```bash
   uv run pytest <test_file> -v
   uv run ruff check <source_file> <test_file>
   uv run mypy <source_file> <test_file>
   uv run python scripts/check_headers.py
   uv run python scripts/scan_forbidden.py
   ```
5. **Git Commit**:
   ```bash
   git add <source_file> <test_file>
   git commit -m "implement <source_file>"
   ```

---

## 4. Master Batch Roadmap

### Completed Batches

- **Batch 1 (Contracts & Core Config)**:
  - `src/asf/contracts/ids.py`
  - `src/asf/config/paths.py`
  - `src/asf/config/loader.py`
  - `src/asf/config/settings.py`
  - `src/asf/config/secrets.py`
  - `src/asf/logging_setup.py`

- **Batch 2 (Platform Adapters & Doctor CLI)**:
  - `src/asf/platform/base.py`
  - `src/asf/platform/fallback.py`
  - `src/asf/platform/sandbox_jobobject.py`
  - `src/asf/platform/sandbox_srt.py`
  - `src/asf/platform/sandbox_bwrap.py`
  - `src/asf/platform/windows.py`
  - `src/asf/platform/linux.py`
  - `src/asf/platform/select.py`
  - `src/asf/doctor/checks.py`
  - `src/asf/doctor/report.py`
  - `src/asf/cli/commands/doctor.py`
  - `src/asf/cli/app.py`

- **Batch 3 (M5 Shared Foundations)**:
  - `src/asf/m5_shared/events/redaction.py` (Redacts private keys, bearer tokens, API keys)
  - `src/asf/m5_shared/workspace/blobs.py` (Content-addressed SHA-256 blob storage)
  - `src/asf/m5_shared/state_store/schema.py` (Forward-only WAL SQLite migrations)
  - `src/asf/m5_shared/state_store/store.py` (Single-writer StateStore with IF-16 optimistic concurrency)
  - `src/asf/m5_shared/events/event_log.py` (Event log with monotonic seq and large blob offload)
  - `src/asf/m5_shared/state_store/outbox.py` (At-least-once outbox relay)
  - `src/asf/m5_shared/events/fanout.py` (EventFanout cursor generator)
  - `src/asf/m5_shared/decisions/broker.py` (HITL DecisionBroker with deadlines and safe defaults)
  - `src/asf/m5_shared/metrics/pricing.py` (Pricing table loader and cost computation)
  - `src/asf/m5_shared/metrics/collector.py` (Call/tool metrics recording and CSV export)
  - `src/asf/m5_shared/metrics/advisories.py` (ResourceAdvisory threshold evaluator)

- **Batch 4 (M5 Shared: Registry, Workspace, Gateway, Runtime)**:
  - `src/asf/m5_shared/registry/compatibility.py` (Contract compatibility classifier: NO_CHANGE, NON_BREAKING, BREAKING)
  - `src/asf/m5_shared/registry/capsules.py` (Markdown capsule renderer for schemas, types, errors)
  - `src/asf/m5_shared/registry/registry.py` (ContractRegistry: contract registration, versioning, verification)
  - `src/asf/m5_shared/workspace/workspace.py` (WorkspaceManager: git worktrees, blob commits, snapshots)
  - `src/asf/m5_shared/gateway/tokenizers.py` (Token counting: tiktoken and flagged fallback estimates)
  - `src/asf/m5_shared/gateway/providers.py` (LangChain chat model construction: OpenAI, Groq, xAI, Gemini, Anthropic, local)
  - `src/asf/m5_shared/gateway/usage_callback.py` (LangChain callback recording call metrics, token counts, costs)
  - `src/asf/m5_shared/gateway/gateway.py` (ModelGateway: role-to-route resolution, fallbacks, retries, structured output)
  - `src/asf/m5_shared/runtime/probes.py` (ResourceProbe: RAM and NVML GPU/VRAM readings)
  - `src/asf/m5_shared/runtime/backends.py` (LocalRuntimeBackend adapters: llama-server, Ollama, External)
  - `src/asf/m5_shared/runtime/local_runtime.py` (LocalRuntime: slot leases, heartbeat, expiry, residency)
  - `src/asf/m5_shared/runtime/calibration.py` (Calibration: tokens/s, VRAM by context, ModelProfile production)

- **Batch 6 (M2 Request)**:
  - `src/asf/m2_request/document_ingestion.py` (MarkItDown extraction, BlobStore storage, media detection, quality scoring)
  - `src/asf/m2_request/prompt_normalisation.py` (Deterministic Unicode/newline cleaning + optional T1 model cleanup)
  - `src/asf/m2_request/repository_intake.py` (Repo profiling, language detection, build/test probing, RepoIndex generation)
  - `src/asf/m2_request/request_understanding.py` (StructuredRequest extraction, TaskType classification, requirement anchoring)
  - `src/asf/m2_request/intake_router.py` (SubmitRequest intake, SHA-256 idempotency key, provenance tagging, outbox emission)
  - `src/asf/m2_request/pipeline.py` (M2 LangGraph StateGraph: branches -> barrier -> normalise -> understand)

---

### Remaining Batches

#### Batch 7: M4 Execution
1. `src/asf/m4_execution/integration/repair.py`
2. `src/asf/m4_execution/verification/test_selection.py`
3. `src/asf/m4_execution/verification/failure_classifier.py`
4. `src/asf/m4_execution/verification/reviewer.py`
5. `src/asf/m4_execution/verification/gate.py`
6. `src/asf/m4_execution/worker/strategies.py`
7. `src/asf/m4_execution/worker/worker_graph.py`
8. `src/asf/m4_execution/scheduler.py`
9. `src/asf/m4_execution/integration/integrator.py`

#### Batch 8: M3 Orchestration
1. `src/asf/m3_orchestration/lifecycle.py`
2. `src/asf/m3_orchestration/planning/modes.py`
3. `src/asf/m3_orchestration/planning/strategies.py`
4. `src/asf/m3_orchestration/planning/test_authoring.py`
5. `src/asf/m3_orchestration/planning/planner_graph.py`
6. `src/asf/m3_orchestration/decomposition/frontier.py`
7. `src/asf/m3_orchestration/decomposition/sizer.py`
8. `src/asf/m3_orchestration/decomposition/rubric.py`
9. `src/asf/m3_orchestration/decomposition/splitter.py`
10. `src/asf/m3_orchestration/decomposition/split_validator.py`
11. `src/asf/m3_orchestration/decomposition/leaf_certifier.py`
12. `src/asf/m3_orchestration/decomposition/decomposition_graph.py`
13. `src/asf/m3_orchestration/escalation.py`
14. `src/asf/m3_orchestration/acceptance.py`
15. `src/asf/m3_orchestration/run_control.py`
16. `src/asf/m3_orchestration/run_graph.py`

#### Batch 9: CLI
1. `src/asf/cli/ui/render.py`
2. `src/asf/cli/ui/menus.py`
3. `src/asf/cli/views/*`
4. `src/asf/cli/project_input.py`
5. `src/asf/cli/run_controls.py`
6. Remaining `src/asf/cli/commands/*`
7. `src/asf/cli/flows.py`
8. `src/asf/cli/app.py` (remaining command wiring)

#### Batch 10: Web
1. `src/asf/web/narrative.py`
2. `src/asf/web/projection.py`
3. `src/asf/web/server.py`
4. `src/asf/web/static/{index.html, app.js, style.css}`

#### Batch 11: Skills
1. Procedures inside `skills/*/SKILL.md` (keep YAML frontmatter intact).
