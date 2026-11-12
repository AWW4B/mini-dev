<!--
FILE: docs/EXECUTION_PLAN.md
ROLE: Ordered execution plan to finish, harden and optimise the product, with the git branch model and the per-unit quality bar.
ARCH REF: M1-M5; all modules
OWNS: Phase order, branch names, hardening checklist, progress ticks
DOES NOT OWN: Implementation code, file headers, the batch file lists (docs/CONTINUATION.md)
CONNECTS TO (external boundaries only):
  - imports from none: none
  - emits/consumes: none
INSTRUCTIONS (strict, imperative):
  1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
  2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
  3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
  4. Open text files with encoding="utf-8" explicitly.
  5. Tick a checkbox only after its unit is merged into main with every check green.
FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
DONE WHEN: (1) `uv run python scripts/check_headers.py` reports no problem for this file.
-->

# Execution Plan: Finish, Harden, Optimise

Written 2026-11-12 for the agent that executes it. Read this file, `AGENTS.md` and `docs/CONTINUATION.md` before doing anything.
Work top to bottom. Do not skip a phase. Tick boxes as units land on `main`.

---

## 0. Measured starting point (2026-11-12, commit b7930ab)

| Check | Result |
|---|---|
| `ruff check src tests` | clean |
| `mypy src` (strict) | clean, 165 files |
| `check_headers.py` | 0 problems (338 headers) |
| `scan_forbidden.py` | **14 hits**, all in `docs/architecture/AI_Software_Factory_Research_and_Decisions.md` (container-runtime names in a comparison table) |
| `pytest` | 139 passed, **204 failed**. Almost all failures are placeholder tests that `raise NotImplementedError("write this test ...")` |
| GitHub CI (`.github/workflows/ci.yml`) | **red on main** because of the two rows above |

Module status:

| Module | Status |
|---|---|
| Contracts (`src/asf/contracts`) | Implemented. **All 17 test files are still placeholders** (84 failing tests). |
| Config, platform, doctor, logging | Implemented. `tests/platform/test_base.py` is still a placeholder. |
| M5 Shared | Implemented (Batches 3, 4 and an unrecorded "Batch 5": context, tools, codeexec, recovery, backup). |
| M2 Request | Implemented (Batch 6). |
| M4 Execution | Stub (Batch 7). |
| M3 Orchestration | Stub (Batch 8). |
| M1 CLI | Only `doctor` and part of `app.py` (Batch 9). |
| M1 Web | Stub (Batch 10). |
| Skills | Procedures empty (Batch 11). |

---

## 1. Git branch model

The user wants each feature on its own branch, all combined on `main`, so a later change to one feature does not disturb the others.

Branches give **history isolation** (one feature = one revertible merge). **Runtime isolation** comes from the file contracts (headers, `CONNECTS TO`) and the tests, so keep both strict; a branch cannot protect a feature whose contract was broken.

Rules:

1. `main` is always green: every check in section 4 passes on the merge commit.
2. One branch per feature group (the groups are listed in each phase). Name: `feat/<module>-<feature>`, `fix/<module>-<topic>`, `chore/<topic>`, `perf/<module>-<topic>`.
3. Branch from the latest `main`. One commit per unit (`implement <file>` / `fix <file>: <what>`), as `CONTINUATION.md` already does.
4. Before merging: `git fetch`, `git rebase origin/main`, run all checks, then
   `git checkout main && git merge --no-ff <branch> -m "merge <branch>: <one line>"`.
   `--no-ff` keeps one merge commit per feature, so `git revert -m 1 <merge>` removes a whole feature cleanly.
5. **Keep merged branches** (do not delete them). They are the per-feature history the user asked for. Push them: `git push -u origin <branch>`, then push `main`.
6. Later changes to a feature: new branch `fix/<same-feature>` from `main`, never reuse an old branch that has fallen behind.
7. Never have two open branches editing the same file.
8. Push only when the user has approved pushing for this session.

---

## 2. Phases

### Phase 0: Green baseline (`chore/green-baseline`)

Goal: CI green on `main` with honest signals, before any feature work.

- [ ] **Forbidden scan false positives.** The research document legitimately names container runtimes when comparing sandboxes. Stop and ask the user to approve one of: (a) add `AI_Software_Factory_Research_and_Decisions.md` to `SKIP_FILES` in `scripts/scan_forbidden.py` (recommended, smallest diff; also update `tests/scripts/test_scan_forbidden.py` if it pins the set), or (b) reword the document. This edits a contract file, so it needs the user's OK.
- [ ] **Placeholder tests must not hide real failures.** In `tests/conftest.py` add a `pytest_runtest_makereport` hookwrapper that turns a `NotImplementedError` whose message starts with `"write this test"` into `xfail` (non-strict). Real failures stay red. This shim is removed in Phase 7.
- [ ] **Record Batch 5** in `docs/CONTINUATION.md` (context, tools, codeexec, state_store backup/recovery) and add a pointer to this file.
- [ ] CI shows green on `main` for ubuntu and windows.

### Phase 1: Tests for already-implemented code (`chore/contract-tests`)

Code that is "done" but untested is not done. Write real tests; no source changes unless a test exposes a bug (then fix it in Phase 2's branch for that module and note it).

- [ ] `tests/contracts/test_*.py`, all 17 files: validation, defaults, frozen/extra-forbid behaviour, JSON round-trip, enum values, every error class's message and hierarchy (`AsfError` subclasses).
- [ ] `tests/platform/test_base.py`.

### Phase 2: Hardening existing code (`fix/<module>-hardening`, one branch per module)

These are defects found in the audit. Each item names the rule it violates. Fix within each file's header contract; if the fix needs a contract change, stop and report.

**2a. Silent exception swallowing (violates every header's ERRORS rule).** About 25 sites follow the pattern `except Exception as _err: _ = _err`. Each one hides a failure. Sites:
`m2_request/document_ingestion.py` (3), `m2_request/pipeline.py` (5), `m2_request/prompt_normalisation.py`, `m2_request/repository_intake.py`, `m5_shared/gateway/gateway.py`, `m5_shared/state_store/recovery.py` (7), `m5_shared/runtime/backends.py` (5), `m5_shared/tools/executor.py`, `m5_shared/context/repo_index.py`, plus the rest from `grep -rn "except Exception" src`.
For each site decide, in this order:
1. Can it be narrowed to the real exception types (`OSError`, `sqlite3.Error`, `httpx.HTTPError`, `ValueError`)? Narrow it.
2. Is degrading correct (header says "degrade through the safe fallback and report it")? Then log it with structlog (`logger.warning(..., exc_info=True)`) **and** surface it in the result (an `extractor`/`degraded` field, a `CheckResult` status, or an event) using only fields that already exist.
3. Otherwise raise the matching `AsfError` subclass from `asf.contracts.errors` with an actionable message.
Also remove the `except (NotImplementedError, Exception)` stub guards in `logging_setup.py`, `doctor/checks.py`, `cli/commands/doctor.py` and `cli/app.py` once the code they guard is real (redaction is real now).

**2b. `m2_request/pipeline.py`**
- [ ] It writes raw SQL `INSERT OR IGNORE INTO outbox` and swallows failures. Its header says events go "via StateStore.commit". Events can be lost silently. Route through `StateStore.commit` as declared; if that is impossible with the current `StateStore` signature, stop and report.

**2c. `m2_request/document_ingestion.py`**
- [ ] Header requires a `DecisionRequest` (kind CLARIFY) for unsupported, oversized or unreadable files. `DecisionBroker` is imported but unused (`noqa: F401`). Implement it.
- [ ] No size limit: the whole file is read into memory (`read_bytes`) and then read again by MarkItDown. Check `path.stat().st_size` against a limit from settings **before** reading; oversized means CLARIFY.
- [ ] `PK\x03\x04` matches every ZIP (xlsx, pptx, jar). Look inside the archive for `word/document.xml` (docx), `ppt/` (pptx), `xl/` (xlsx) using `zipfile`.
- [ ] Header says alternates run on a failed **quality check**; the code only falls back on empty output. Run the alternates when `quality_score` is below a threshold and keep the best-scoring result (at most 2 alternates).
- [ ] Create `MarkItDown()` once per process (module-level lazy singleton), not per call.
- [ ] Optional Docling path (header rule 9): use it only if `importlib.util.find_spec("docling")` succeeds. It is the architecture's recommended PDF default and the only path with OCR.

**2d. `m5_shared/context/repo_index.py`: memory**
- [ ] It keeps the full text of every `.py/.md/.toml/.json/.txt` file in `self._file_contents` with no size cap. On a large repo this is hundreds of MB. Keep only symbols, sizes and hashes in memory; read file text lazily on demand; skip files larger than a cap (for example 1 MB) and binary-looking files. Keep the public API unchanged.

**2e. `m5_shared/workspace/blobs.py`**
- [ ] Raises bare `FileNotFoundError`; header requires an `AsfError` subclass.
- [ ] Temp file is always `<digest>.tmp`: two processes storing the same blob race on it. Use `tempfile.NamedTemporaryFile(dir=target.parent, delete=False)` then `os.replace`, and treat "target already exists" after the race as success (Windows `replace` can raise `PermissionError` while another process holds the file).

**2f. General memory and speed audit (each implemented module).** For each file check and fix:
- unbounded `fetchall()` on tables that grow (events, metrics, tasks): iterate the cursor or page with `LIMIT`/`seq >`;
- whole-file reads where streaming works (`hashlib` in 1 MB chunks);
- per-call construction of expensive objects (tokenizers, model clients, regex compiles): cache at module level or on the instance;
- SQLite: confirm WAL, `synchronous=NORMAL`, one write transaction per batch instead of per row;
- `rglob("*")` walks that descend into skip dirs: prune with `os.walk` and edit `dirnames` in place.

### Phase 3: M4 Execution (Batch 7)

Branches: `feat/m4-verification` (test_selection, failure_classifier, reviewer, gate), `feat/m4-worker` (strategies, worker_graph), `feat/m4-integration` (repair, integrator), `feat/m4-scheduler` (scheduler). File order as in `CONTINUATION.md`. If a file's `CONNECTS TO` imports from a stub, implement the callee first.

- [ ] verification   - [ ] worker   - [ ] integration   - [ ] scheduler

### Phase 4: M3 Orchestration (Batch 8)

Branches: `feat/m3-lifecycle` (lifecycle, escalation, acceptance), `feat/m3-planning` (modes, strategies, test_authoring, planner_graph), `feat/m3-decomposition` (frontier, sizer, rubric, splitter, split_validator, leaf_certifier, decomposition_graph), `feat/m3-run-control` (run_control, run_graph).
Keep the architecture rule: the orchestrator is deterministic code; leaf/split decisions use measurement plus the single T1 rubric call (architecture doc, Part 8). Never let a model approve its own split.

- [ ] lifecycle   - [ ] planning   - [ ] decomposition   - [ ] run-control

### Phase 5: M1 CLI (Batch 9)

Branches: `feat/cli-ui` (render, menus, views), `feat/cli-commands` (one commit per command file), `feat/cli-flows` (project_input, run_controls, flows, app wiring).

- [ ] ui   - [ ] commands   - [ ] flows

### Phase 6: Web and Skills (Batches 10, 11)

Branches: `feat/web-viewer` (narrative, projection, server, static), `feat/skills` (each `skills/*/SKILL.md`, keep YAML frontmatter).
The web server is read-only (there is a test that no write routes exist) and must bind to localhost only.

- [ ] web   - [ ] skills

### Phase 7: End to end and performance (`perf/e2e`)

- [ ] Remove the placeholder-to-xfail shim from Phase 0; `pytest` must have zero xfails from placeholders.
- [ ] `scripts/smoke.py` runs one small request end to end with a local or stub model on Windows and Linux.
- [ ] Profile one smoke run: `uv run python -X importtime -m asf ...` (startup), `cProfile` (hot paths), `tracemalloc` peak (memory). Record the numbers in this file and fix the top three offenders.
- [ ] Lazy-import heavy modules in the CLI (langchain, markitdown, tree-sitter) so `factory --help` and `factory doctor` start fast.

---

## 3. Per-unit quality bar

For every file, in this order:

1. Read only the target header and the files under its `CONNECTS TO`. Write down (in your head or a scratch note) every obligation in INSTRUCTIONS, ERRORS and DONE WHEN.
2. **Tests first.** One test per obligation, plus: the failure path for each error the header names, an empty or minimal input, a boundary (size limit, LIMIT), a Windows-style path where paths are involved, and idempotency where the header claims it. Use fixtures from `tests/conftest.py` and `tmp_path`; no network, no real models.
3. Implement the smallest code that passes. Strict typing, no `Any` unless the header's types force it, no `# type: ignore` without a reason comment, no broad `except`.
4. Memory and speed: bounded reads, cursors not `fetchall` on growing tables, no per-call construction of expensive objects, no quadratic loops over repo files.
5. Self-review the diff before committing: every obligation covered? any swallowed exception? any hardcoded path or `shell=True`? any name or signature changed? any duplicated helper that exists under `CONNECTS TO`?
6. Run section 4. Commit only when all pass.

Stop and report to the user (do not work around) when: a header contract must change, a dependency must be added or upgraded, a test can only pass by weakening the header's requirement, or behaviour differs between Windows and Linux in a way the platform layer cannot hide.

---

## 4. Checks (all must pass before every merge to main)

```bash
uv run pytest <test_file> -v
uv run pytest -q
uv run ruff check src tests scripts
uv run mypy src
uv run python scripts/check_headers.py --coverage
uv run python scripts/scan_forbidden.py
```
