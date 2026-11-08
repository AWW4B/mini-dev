# AI Software Factory — Architecture Decisions and Technology Research

**Companion to:** `AI_Software_Factory_Architecture.drawio` (17 pages: index, HLD, 11 LLD pages, 2 sequence diagrams, contracts, failure matrix)
**Research date:** 28 October 2026
**Target machine:** 16 GB RAM, RTX 4050 6 GB VRAM, Windows (Linux possible)
**Status:** proposal for review. Nothing here has been benchmarked on your hardware yet. Section 9 is the plan for doing that.

> **Evidence labels used throughout**
> **[V]** verified from a primary source or the project's own docs during this research (links in §10)
> **[S]** from a secondary source (article or aggregator) and worth re-checking
> **[K]** long-established fact from prior knowledge, not re-fetched today
> **[U]** unverified or changing quickly. Treat it as a question, not a fact.

---

## Part 1 — Deliverable C: Architecture decision summary

### 1.1 The ten corrections that matter most

The full list (C1–C18) is on page 00 of the draw.io file. These ten change behaviour, not just layout.

| # | Original design | Correction | Where |
|---|---|---|---|
| C1 | Decomposition was one "too complex?" judgement plus a depth/cycle guard. A fixed depth cap contradicts the brief. | A persisted work-list. Each node is **sized deterministically** against a *measured* model profile (C_eff, files, interfaces, risk). A planning-tier model only proposes splits; a deterministic validator accepts or rejects them. Termination comes from the **α-progress rule** (every child ≤ 0.8 × parent size), per-node split budgets, run budgets, cycle checks and the cancel token. **No fixed depth.** | p05, p06 |
| C2 | Children were created without contracts, and the task tree was never persisted. | Each child carries a contract slice. Children, edges, contracts and idempotency keys commit in **one transaction**. | p05, p09 |
| C4 | The worker wrote files and registered signatures *before* verification. | Every attempt runs in an **isolated branch/worktree**. Merge and registry update happen only after the gate passes. Dependents consume **pinned signatures**, never generation history. This is your "treat the last file as a function" rule. | p07, p08, SEQ-1 |
| C5 | Integration had no trigger and re-assembled everything. | **Bottom-up integration.** A composite is integrated when all its children are verified. Failures create targeted repair leaves inside that subtree. | p08 |
| C6 | Two queues each enforced "max 1–2". | The **scheduler owns readiness**; the **Local Runtime owns inference-slot leases**. `max_slots` (1 or 2) comes from calibration, not from the design. | p07, p11 |
| C7 | Context management sat inside M3 and could silently truncate. | A shared **Context & Memory Service** (M5) builds every prompt under a token budget. If the must-have items don't fit, it returns **CONTEXT_OVERFLOW**, which drives a re-split. This is the deterministic link between context budget and task granularity. | p12, p05 |
| C8 | HITL requests were ad-hoc edges into the chat and were lost on restart. | A **durable Decision Broker** with deadlines and safe defaults (it never auto-approves risky kinds), plus a single Decision Inbox. Unrelated subtrees keep running. | p10, p02 |
| C9/C10 | Retry counters could multiply, and there was no crash recovery. | One **attempt ledger per task**, with separate counters for model failures, infrastructure faults and interruptions. **Startup reconciliation** expires leases, resets worktrees, re-arms decisions and restores the frontier. | p06, p09, SEQ-2, p16 |
| C3 | Debug/feature skipped planning, and nothing ingested an existing repository. | New **Repository Intake** (snapshot, build/test detection, static index, baseline run). The Planner gains **DIAGNOSIS / IMPACT / REFACTOR** modes. | p03, p04 |
| C12 | The HLD hard-coded a provider and a runtime. | A technology-neutral **Model Gateway** with tier *roles* (T0 code, T1 small local, T2 local coder, T3 remote planner) and provider adapters. | p11 |

### 1.2 Key design decisions (recommended defaults)

1. **The orchestrator is deterministic application code; models are called as functions.** The run, task graph, budgets and leases live in a transactional store, not in any framework's agent state. Every framework below is replaceable because of this.
2. **Decide sizing by measurement and use the LLM for judgement.** Token estimates, file and interface counts, and calibrated success rates make the leaf/split decision. One small rubric call (T1) scores ambiguity and coupling. The expensive model only proposes splits; it never decides whether its own split is acceptable.
3. **Lazy, interleaved decomposition.** Contracts are fixed top-down first. Deeper subtrees are expanded when their dependencies are near completion, so they plan against *implemented* interfaces rather than speculation. This follows ADaPT ("decompose only as needed") and makes it contract-aware. [V]
4. **Verification is deterministic first.** Format, lint, type, build, selected tests and contract tests decide pass/fail. A reviewer model is optional and policy-triggered (risky paths, low coverage, public API).
5. **One local inference slot is the design point.** Two slots is a runtime setting that calibration may enable. The scheduler prefers tasks for the model already loaded, so the system doesn't thrash on model swaps.
6. **No automatic deployment.** The run ends with a report: deliverables, traceability matrix, decision log.

### 1.3 Recommended MVP boundaries

**In scope for v1**
- Single user, single machine, one active run.
- Python projects first; TypeScript second.
- New build, debug and feature task types. Refactor follows once characterisation tests work.
- PDF, DOCX and MD input.
- The full recursive decomposition engine with budgets.
- Local T2 coder plus an optional remote T3 planner.
- Deterministic verification and bottom-up integration.
- Event-log-based group chat, dashboard with measured/estimated tags, and crash recovery.

**Out of scope for v1**
- Multi-user and multi-tenant.
- Automatic deployment.
- Automatic HLD/LLD diagram generation (a future feature).
- Embedding-based semantic code search (optional later; see §3G).
- Distributed workers.
- Mutation testing as a gate (it is an evaluation tool only).

### 1.4 Major risks

| Risk | Why it matters | Mitigation built into the design |
|---|---|---|
| **The local 7–8B coder is too weak for many leaves.** | Leaves fail or are split too finely, and the run cost explodes. | Calibrated leaf thresholds; α-progress plus run node budget; a "higher tier once" escalation; Experiment E3 sizes the threshold empirically. |
| **Remote free tiers change or vanish.** | Planning stalls. | Fallback chain, then degraded mode (T2 local planner plus mandatory human plan approval). Spend caps live in RunBudget. Never depend on one provider. |
| **Windows resource overhead.** | It eats into the 16 GB RAM, so MoE offload models may not fit. | Recommend WSL2 or native Linux for the factory (open decision D6); measure in E1. |
| **Over-decomposition into many tiny leaves.** | Integration overhead and context loss. | The leaf profile has a *minimum* meaningful size too (a leaf must own at least one contract operation plus its tests). Merging siblings is allowed when the split validator sees children under the minimum. |
| **Supply-chain compromise of the AI tooling.** | The LiteLLM PyPI packages 1.82.7 and 1.82.8 were malicious on 24 March 2026 [S]. | Exact pins plus hashes, a minimal dependency set, secrets outside the factory process environment where possible, and a sandbox without network. |
| **Prompt injection via documents, repositories or tool output.** | Destructive tool calls or exfiltration. | Provenance tags; permissions enforced by the executor, not by prompts; no network in the sandbox; destructive kinds always go to HITL. |

### 1.5 Technology choices that need your approval

| ID | Decision | Recommendation | Alternative |
|---|---|---|---|
| T-1 | Implementation language | **Python 3.12+** (ecosystem for agents, testing, document parsing) | TypeScript (Node) |
| T-2 | Durable execution | **Own state machine on SQLite**, optionally hosted by **DBOS Transact** (MIT, SQLite supported) after the PoC | LangGraph checkpointers; Temporal is too heavy |
| T-3 | Local inference runtime | **llama.cpp `llama-server`** (MIT) | Ollama (MIT) for convenience |
| T-4 | T2 local coder | Benchmark **Qwen3-8B / Qwen2.5-Coder-7B** (fully on GPU) vs **gpt-oss-20b** (MoE offload) | Qwen3.6-35B-A3B at low-bit quantisation (experimental) |
| T-5 | T3 remote planner | Provider-neutral. Pick 1 paid + 1 free fallback after E9. | Local-only degraded mode |
| T-6 | Coding harness | **Own minimal harness** (mini-swe-agent-style loop) | Aider; OpenHands Software Agent SDK |
| T-7 | Document ingestion | **Docling** (MIT) + **MarkItDown** (MIT) fast path | Marker (check its weights licence) |
| T-8 | Sandbox | **WSL2/Linux + bubblewrap** (via Anthropic `srt`, Apache-2.0) for commands; Docker for service-dependent tests | Docker Sandboxes (sbx), heavier |
| T-9 | Host OS | **WSL2** now, native Linux if RAM is short | Native Windows |

### 1.6 Open questions (also on page 00)

- **D1** Plan-approval policy: always, or only for new builds and breaking changes?
- **D2** Numeric budgets (α, attempts, 0.6·C_eff margin). Set by benchmark.
- **D3** Is the reviewer model on by default?
- **D4** HITL deadline and safe default per decision kind.
- **D5** Remote provider(s) and monthly spend cap.
- **D6** Windows + WSL2, or native Linux?
- **D7** The v1 language list.

---

## Part 2 — How to read this document

- Technologies are compared **per architectural responsibility** taken from the finalized LLDs (page references like "p07" point into the draw.io file).
- The 12 fields the brief requires are covered in every table, merged into 7 columns so the tables stay readable:
  - **Role / maturity**: category + maturity
  - **Licence / cost**: licence + cost
  - **Fit**: capabilities + advantages
  - **Limits / hardware**: limitations + hardware fit
  - **Integration / lock-in**: integration + lock-in
- Benchmark figures are quoted only when a source gives them. Throughput on your GPU is **not** estimated here. It is the first thing the calibration job measures (p11, E1).
- "Do it in application code" is a legitimate verdict. Several responsibilities are small, central and domain-specific enough that a framework adds more risk than it removes.

---

## Part 3 — Technology comparisons by layer

### A. Agent orchestration and workflow execution

**What the architecture actually needs** (p04–p06, p09):
- A durable run state machine and a recursive task graph with leases and budgets.
- Cancel, pause and resume.
- HITL that survives restarts.
- Idempotent steps and crash reconciliation.

Most "agent frameworks" model a *conversation* graph, not a *work* graph. That mismatch is the main selection criterion.

| Technology | Role / maturity | Licence / cost | Fit | Limits / hardware | Integration / lock-in | Verdict |
|---|---|---|---|---|---|---|
| **Own state machine on SQLite** | Deterministic orchestrator; well-known pattern | n/a | Exact semantics for TaskNode states (p06), attempt ledger, leases, outbox. Trivial to inspect and test. | You write retries, timers and recovery yourself (≈ the logic already drawn on p09/SEQ-2). | Zero lock-in; frameworks stay at the edges | **Strong candidate (default)** |
| [DBOS Transact (Python)](https://github.com/DBOS-project/dbos-transact-py) | Durable-execution library; actively developed (monthly releases in 2026) [V] | MIT [V]; free | Durable workflows checkpointed to a DB. Resumes from the last completed step. Queues with per-queue/per-process concurrency limits. Pause/resume/restart workflows. **Supports SQLite** as the system DB ("Postgres is recommended for production") [V]. Pydantic AI integration [V]. | SQLite mode polls rather than using LISTEN/NOTIFY [V]. Cooperative step timeouts were not yet in Python as of July 2026 [V]. | Library inside your process; moderate lock-in (decorators) | **Strong candidate to host the state machine; PoC first** |
| [LangGraph](https://www.developersdigest.tech/blog/langchain-langgraph-whats-new-2026) | Graph agent runtime; very active (`langgraph` 1.2.16, Oct 2026) [S] | MIT [K] | Checkpointers, `interrupt()` with response schemas (1.2.12), per-node timeouts, error handlers, drain-and-resume (1.2.0) [S]. Good for *agent-internal* loops (worker step loop, planner critique loop). | An interrupted node re-executes from its first line on resume, so side effects must be idempotent [S]. State is graph-shaped, which is awkward for a large dynamic task DAG with leases. | Moderate–high if the task graph lives in LangGraph state | **Alternative** (inner loops only) |
| [Pydantic AI](https://pydantic.dev/docs/ai/integrations/durable_execution/overview/) | Typed agent/LLM-call library; active | MIT [K] | Typed structured outputs, model-agnostic, durable execution via Temporal/DBOS integrations [V]. | Not a task-graph scheduler. | Low; use as the "model call" layer | **Strong candidate for typed model calls** (complements, doesn't replace, the orchestrator) |
| [Temporal](https://www.pkgpulse.com/guides/temporal-vs-restate-vs-windmill-durable-workflow-2026) | Durable workflow engine; established | MIT [S] | Gold-standard durability, timers, signals, cancellation. | Needs a server plus DB (Postgres/MySQL/Cassandra); the dev mode loses state on restart [S]. Too heavy for 16 GB alongside a model. | High | **Unsuitable for MVP** |
| [Restate](https://www.pkgpulse.com/guides/temporal-vs-restate-vs-windmill-durable-workflow-2026) | Durable execution server; emerging/active | BSL [S] | Single binary, embedded RocksDB [S]. | A separate server process; BSL licence. | Medium | **Experimental alternative** |
| Prefect / Hatchet / Windmill | Workflow/orchestration platforms | Prefect Apache-2.0 [K]; Windmill AGPLv3 [S]; Hatchet [U] | Retries, scheduling, UIs. | Built for data/ops pipelines, server components, heavier footprint. | Medium–high | **Unsuitable for MVP** |
| CrewAI / Microsoft Agent Framework / Google ADK / OpenAI Agents SDK | Multi-agent frameworks | Mostly MIT/Apache [K] | Role-based agents, handoffs. | Conversation-centric; parallel-agent assumptions; little to offer a deterministic, single-slot work graph. | Medium | **Unsuitable as core**; possibly useful for prototypes |

**Overlap note:** DBOS and LangGraph both offer durability. Use **at most one** for durability. If LangGraph is used, restrict it to stateless inner loops whose checkpoints are disposable, and keep the source of truth in the State Store.

### B. Coding-agent harnesses

**What the architecture needs** (p07):
- A bounded tool loop driven by a **scoped ContextPack**.
- File writes limited to `allowed_files`, with every tool call going through the Tool Executor.
- Works with a 7–20B local model behind an OpenAI-compatible endpoint.
- Is called sequentially and returns a change set.

A *harness* is the loop and tools around a model. It is not the orchestrator, and it is not the model.

| Technology | Role / maturity | Licence / cost | Fit | Limits / hardware | Integration / lock-in | Verdict |
|---|---|---|---|---|---|---|
| **Own minimal harness** | ~300–800 lines: step loop, edit tool, run tool, budget | n/a | Exactly the policy hooks needed (lease id, allowed files, newest-evidence-only, step budget). A 2026 source-code study of 11 harnesses found benchmark results don't track loop sophistication; the 100-line mini-swe-agent scores in the same range as much larger systems [V]. | You maintain edit formats and parsing. | None | **Strong candidate (default)** |
| [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) | Minimal bash-only agent; v2, active | MIT [V] | No tool-calling interface needed (good for weak local models). Each action is an independent `subprocess.run` [V]. Reports > 74% SWE-bench Verified with strong models [V]. | Bash-only means no structural file-scope enforcement unless wrapped. Unbounded message list [V]. | Low; use as a baseline/reference | **Use as baseline in benchmarks; borrow the design** |
| [Aider](https://botmonster.com/ai/aider-model-agnostic-ai-pair-programmer/) | Pair-programming CLI; mature | Apache-2.0 [K] | Tree-sitter **repo map** under a token budget; many edit formats tuned for weaker models; works with local models [V for repo-map design via harness study]. | Interactive-first; no sandbox [V]; harder to drive with strict file-scope policy. | Medium | **Alternative harness for T2**; reuse the repo-map idea |
| [OpenHands + Software Agent SDK](https://rywalker.com/research/openhands) | Full platform + composable Python SDK; very active | MIT core; `enterprise/` source-available [S] | Docker sandboxed runtime, model-agnostic via LiteLLM [S]; MLSys 2026 paper on the SDK [V]. | Heavier (Docker runtime); designed for capable models and parallel agents. | Medium–high | **Alternative** for a later "rich runtime" mode |
| SWE-agent | Research agent; established | MIT [K] | Agent-computer interface design. | Superseded by mini-swe-agent for our use. | Medium | Reference only |
| Claude Code / Codex CLI / Gemini CLI / OpenCode / Goose | Product agents | Various; Codex/Gemini CLIs Apache-2.0 [K]; Claude Code proprietary [K] | Excellent native sandboxes (Codex, Gemini CLI) [V]. | Tied to specific providers or designed for frontier models; the factory needs to control the loop. | High | **Unsuitable as the T2 harness**; useful for studying sandbox/permission design |

### C. Recursive decomposition and task planning (research and algorithms)

| Approach | What it contributes | Risks | Use in this design |
|---|---|---|---|
| **ADaPT: as-needed decomposition** ([paper](https://arxiv.org/html/2311.05772v2)) | Try the executor first; decompose only on failure; recursive with And/Or plans. Large gains over ReAct and Plan-and-Execute on ALFWorld (71.6% success, up to +28.3 pts), WebShop and TextCraft [V]. | ADaPT uses a max depth, and its tasks are not software with contracts. | Adopted as **lazy expansion + re-split on SPEC_TOO_LARGE** (p05). Its depth cap is replaced by the α-progress measure. |
| **Hierarchical task networks (HTN)** [K] | Formal method/operator decomposition and preconditions. | Requires hand-written methods. | Inspires typed node kinds (composite / leaf / integration / repair) and "method templates" per task type (e.g. CRUD module → model, repository, service, API, tests). |
| **Contract-first / design-by-contract** [K] | Interfaces fixed before implementation; contract tests. | Contracts can be wrong early. | Registry versioning with compatibility checks and HITL for breaking changes (p09). |
| **Dependency DAG + topological scheduling, critical-path priority** [K] | Classic, deterministic. | — | Split validator (cycle check) and scheduler ranking (p05, p07). |
| **Well-founded measure for termination** [K] | Guarantees recursion ends without a depth cap. | The size estimate is approximate. | α-rule on S(n) = est_in + est_out; violations are rejected by the validator, not trusted. |
| **Calibrated sizing (empirical success curves)** | Thresholds learnt per model from real pass rates. | Needs a calibration corpus. | ModelProfile success table (p11, E1/E3). |
| Recursive delegation / recursive LM approaches [U] | Recursive sub-calls over large inputs. | Mostly evaluated on long-context QA, not codegen. | Watch-list only (§5). |

**How to avoid the classic failure modes**

| Failure mode | Control |
|---|---|
| Over-decomposition | Minimum leaf content; the validator merges children under the minimum; a run node budget with an 80% alert. |
| Oversized leaves | The CONTEXT_OVERFLOW dry-run before certification; SPEC_TOO_LARGE re-split after execution. |
| Cycles | Topological sort on every commit. |
| Repeated work | Idempotency keys `hash(parent, normalised goal, contract slice)`; VERIFIED tasks are never re-run after a crash. |
| Context leakage | Workers see only the pinned signatures, allowed files and newest failure evidence. |

### D. Models and inference runtimes

**Hardware reality.** 6 GB VRAM holds a dense 7–8B model at ~4-bit (≈ 4.7 GB for `qwen2.5-coder:7b` Q4_K_M), but only with a short context. Real usage is the weights plus 2–6 GB of KV cache, and an 8-bit KV cache roughly halves that [S]. Advertised context lengths (128K–262K) are irrelevant at this size. **C_eff must be measured.** MoE models with ~3B active parameters can offload experts to CPU RAM, but the *total* weights still have to fit in RAM + VRAM.

**Runtimes**

| Technology | Role / maturity | Licence / cost | Fit | Limits / hardware | Integration / lock-in | Verdict |
|---|---|---|---|---|---|---|
| [llama.cpp `llama-server`](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) | Inference server; very mature, very active | MIT [K] | OpenAI-compatible API; **JSON-schema/grammar-constrained output** (`--json-schema`, `--grammar`); tool calling; **MoE expert offload** (`--n-cpu-moe`, `--cpu-moe`, `-ot`); **KV-cache quantisation** (`-ctk/-ctv`); **parallel slots** (`-np`); `--metrics` endpoint [V] | Manual model management | Low (OpenAI-compatible) | **Strong candidate (default)**. Every knob the Local Runtime (p11) needs is exposed. |
| [Ollama](https://github.com/ollama/ollama) | Local model manager/server; mature | MIT [V]; Windows installer [V] | Easiest setup; model library; OpenAI-compatible API and structured outputs [K]. Default 4096-token context, `OLLAMA_KV_CACHE_TYPE` [S]. | Fewer low-level knobs than llama.cpp; its own model store | Low | **Alternative** (convenience) |
| LM Studio | Desktop app + server | Proprietary app [K] | GUI, MLX/llama.cpp engines | Not OSS | Medium | Unsuitable as a core dependency |
| vLLM / SGLang | High-throughput servers | Apache-2.0 [K] | Batching, paged attention | Linux/CUDA-first, aimed at larger VRAM; no benefit at one slot on 6 GB [K] | Low | **Unsuitable for this hardware** |
| ExLlamaV2/V3 | GPU-only fast inference | MIT [K] | Very fast EXL quantisations | GPU-only, so no MoE CPU offload path | Low | Experimental |

**Local coder candidates (T2) and small helpers (T1).** All need validating in E1/E5.

| Model | Size / type | Licence | Fits 6 GB VRAM + 16 GB RAM? | Notes | Verdict |
|---|---|---|---|---|---|
| Qwen2.5-Coder-7B-Instruct | 7B dense | Apache-2.0 [K] | **Yes**, fully on GPU at Q4 (4.7 GB download) with a short context [S] | Most-pulled local coding family [S]; no tool-calling finesse | **Baseline T2** |
| Qwen3-8B | 8B dense | Apache-2.0 [K] | Yes at Q4, ≈ 5–7 GB [S] | Better general reasoning/tool use than 2.5-Coder [U] | **T2 candidate; also T1** (same model avoids swaps) |
| gpt-oss-20b | MoE (~3.6B active) [K] | Apache-2.0 [K] | **Borderline**: "runs on 16 GB RAM" [S]; needs `--n-cpu-moe` offload; Windows overhead may break it | Not code-specific [S] | **T2 candidate if E1 shows it fits** |
| Qwen3.6-35B-A3B | MoE 35B / 3B active | Apache-2.0 [S] | **Probably not** at Q4 (14–24 GB depending on quant [S]); only aggressive low-bit | Strong agentic coder per secondary sources [S] | Experimental (low-bit) |
| Qwen3-Coder-30B-A3B | MoE 30B / 3B active | Apache-2.0 [K] | No at Q4 (~24 GB class [S]) | — | Unsuitable now |
| Qwen3-Coder-Next | MoE 80B / 3B active | [U] | **No**: ~46 GB at 4-bit [V] | — | Unsuitable |
| Devstral (24B) | dense | Apache-2.0 [K] | No (14 GB at Q4 [S]; mostly CPU) | 46.8% SWE-bench Verified [S] | Unsuitable for the interactive T2 role; possible slow overnight fallback |
| Qwen3-1.7B/4B, Gemma 3 4B | small dense | Apache-2.0 / Gemma terms [K] | Yes | T1 rubric, classification, summaries | T1 only if a second resident model fits; otherwise use the T2 model for T1 |

**T1/T2 swap rule.** With one slot, loading a separate T1 model evicts T2. The default is to **reuse the T2 model for T1 tasks**. A separate tiny T1 model is used only if calibration shows both stay resident.

**Remote tier (T3).** Free tiers are unstable, and specifics should be treated as **[U]**:
- An aggregator reports that Gemini's free tier became Flash-only in 2026, with unpublished per-project limits visible in AI Studio [S/U].
- Paid tiers have enforced spend caps from 1 April 2026 [S/U].

Design consequences:
1. Provider adapters behind the Model Gateway.
2. An ordered fallback chain.
3. A hard spend cap in RunBudget.
4. Degraded local mode with mandatory plan approval.

Use the remote tier where it buys the most: planning, splitting, hard diagnosis, and escalation after local attempts are exhausted.

### E. Tool calling and integration protocols

| Technology | Role / maturity | Licence / cost | Fit | Limits | Integration / lock-in | Verdict |
|---|---|---|---|---|---|---|
| **In-process tools with JSON Schema** (Pydantic models) | Simplest; mature | n/a | Fast, typed, executor-enforced permissions, no extra processes | Not reusable by external agents | None | **Default for internal tools** |
| [Model Context Protocol](https://modelcontextprotocol.io/specification/2026-07-28/changelog) | Open protocol, now under the Linux Foundation's Agentic AI Foundation [V] | Open spec | Latest stable revision **2026-07-28** [V]: stateless requests (no `initialize` handshake), `server/discover`, Multi Round-Trip Requests replacing server-initiated requests, tasks moved to an official extension, JSON Schema 2020-12 for tool schemas, OpenTelemetry trace-context keys in `_meta`; Roots, Sampling and Logging deprecated [V]. | Version churn; MCP servers are a common prompt-injection and supply-chain surface | Low (open standard) | **Strong candidate for external tools** (e.g. code-intelligence servers), behind the Tool Executor's permission layer |
| OpenAI-compatible function calling | De-facto LLM API convention | n/a | Supported by llama.cpp/Ollama and most providers [V/K] | Weak local models produce malformed calls; needs grammar/schema constraints and repair | Low | **Use at the model boundary**, with schema-constrained decoding |
| A2A (agent-to-agent) | Inter-agent protocol [K] | Open | Cross-vendor agent delegation | The factory's agents are internal; no need | — | Not needed |

**The distinction to keep.** *Protocol* (MCP) ≠ *framework* (Pydantic AI / LangGraph) ≠ *tool implementation* (ripgrep, pytest, git). The Tool Executor (p12) is the single place where permissions, timeouts and output sanitising happen, whatever the transport.

### F. Skills and reusable capabilities

| Option | Fit | Verdict |
|---|---|---|
| [Agent Skills (SKILL.md)](https://agentskills.io/) | An open format created by Anthropic: a folder with `SKILL.md` (name and description metadata plus instructions) and optional scripts and references. Uses **progressive disclosure**: discovery loads only name and description, activation loads the full file, execution loads extra files on demand [V]. This matches the Tools & Skills Registry design on p12. | **Strong candidate** as the skill package format |
| Prompt templates in code | Simple, versioned with code | Fine for the fixed system prompts of T1/T2 roles |
| Sub-agents | An extra model context per role | Use only when a role needs a different model or tier (planner, reviewer). Too costly on a single slot otherwise. |

**When to use which**

| Use | When |
|---|---|
| Deterministic function | The step can be specified exactly (parsing, sizing, validation, test selection). |
| Tool | The model needs to *act* (edit, run, search). |
| Skill | The model needs a *procedure* or domain checklist that is too large to keep in every prompt (e.g. "how to write a FastAPI router + tests in this repo's style", "reproduce-then-fix procedure"). |
| Sub-agent | A different model, tier or context isolation is required. |
| Prompt instruction | Short, always-relevant rules. |

**Skills worth writing for v1** (capabilities, not existing packages):
- request-structuring
- split-proposal rubric
- write-tests-from-acceptance-criteria
- python-module-from-contract
- reproduce-bug-as-failing-test
- characterisation-tests-for-refactor

I am not aware of a verified, maintained public skill package for any of these; they should be authored and versioned in the project repository.

### G. Context engineering and memory

| Approach | Evidence / maturity | Fit for a sequential local coder | Verdict |
|---|---|---|---|
| **Tiered, budgeted ContextPack** (P0 spec + acceptance → P5 newest failure) | Standard practice [K] | Core of p12; gives the CONTEXT_OVERFLOW signal | **Default** |
| **Signature-only views of dependencies** (from the Registry) | Contract-first [K] | Keeps prompts small; enforces "consume interfaces, not history" | **Default** |
| **Repo map with tree-sitter + ripgrep** | Used by Aider; the 2026 harness study found **no** studied system uses embedding search; all rely on ripgrep, tree-sitter, glob and AGENTS.md-style files [V] | Cheap and deterministic | **Default** |
| LSP-backed symbol tools (e.g. [Serena](https://github.com/oraios/serena) via MCP) | Active; 40+ languages [V] | Precise references and renames | **Alternative**. **Licence caution:** the application is GPL-3.0-or-later; only the SolidLSP part is MIT [V]. Run it as a separate MCP process, not linked into the factory. |
| Embedding-based semantic search | Mature tech [K] | Extra model and RAM, index maintenance; little evidence of need at this scale | **Exclude from MVP**; revisit with E4 |
| Conversation compaction (T1 summaries) | Common [K] | Only for chat history; never for task specs or contracts | **Use, bounded** |
| Decision log / ADR-style project memory with source-hash invalidation | [K] | Prevents stale memory | **Default** |

### H. State, persistence and recovery

| Technology | Role / maturity | Licence / cost | Fit | Limits / hardware | Integration / lock-in | Verdict |
|---|---|---|---|---|---|---|
| **SQLite (WAL mode)** | Embedded DB; extremely mature | Public domain [K] | One file, transactions, outbox table, near-zero RAM, easy backup (online backup API) | One writer at a time (fine for one run) | None | **Default State Store** |
| PostgreSQL | Server DB; mature | PostgreSQL licence [K] | Needed only for multi-user or concurrent writers | ~100s of MB RAM | Low | Later |
| **git (per-project repo, worktrees)** | VCS; mature | GPL-2.0 tool, invoked as a binary [K] | Branch per attempt, merge after the gate, tags as checkpoints | Worktree hygiene needed (GC on p09) | None | **Default Artifact & Workspace Store** |
| Content-addressed blob folder (sha-256) | Pattern [K] | n/a | Documents, logs, ContextPack manifests | — | None | **Default** |
| Framework checkpointers (LangGraph, DBOS system tables) | See §A | — | Only for the framework's own internal state | Must not be the source of truth for the task graph | — | Secondary |

### I. Verification, testing and repair

| Technology | Licence | Role | Verdict |
|---|---|---|---|
| pytest (+ pytest-xdist off, + coverage.py) | MIT / Apache-2.0 [K] | Unit, integration and acceptance tests | **Default** |
| Ruff (lint + format) | MIT [K] | Fast static gate | **Default** |
| Pyright or mypy | MIT [K] | Type gate (signature contract enforcement) | **Default** (Pyright is faster) |
| Hypothesis | MPL-2.0 [K] | Property tests for contract invariants | **Default for contract tests** |
| Schemathesis | MIT [K] | OpenAPI-driven API contract tests | When modules expose HTTP APIs |
| pytest-testmon or an import-graph test selector | MIT [K] | Test selection by change impact | **Alternative**; own import-graph selector is simpler to control |
| mutmut / cosmic-ray | BSD / MIT [K] | Mutation testing | **Evaluation only** (measures test strength of generated suites), not a gate |
| Pact | MIT [K] | Consumer-driven contracts between services | Later (multi-service projects) |
| Reviewer model (T3 or a different local model) | — | Findings on risky diffs | **Optional, policy-triggered** |

**Hybrid verification policy.** Deterministic gates decide. The reviewer can only *add* blocking findings, never pass a failing gate. Failure classes route ownership (p08):
- local bug → worker
- too large → decomposition
- contract mismatch → planner
- environment → infrastructure retry
- flaky → rerun once, then quarantine

### J. Sandboxing and security

| Technology | Role / maturity | Licence | Fit | Limits / hardware | Verdict |
|---|---|---|---|---|---|
| [Anthropic sandbox-runtime (`srt`)](https://rywalker.com/research/local-agent-sandboxes) | OS-level process sandbox; uses Seatbelt (macOS) and bubblewrap (+ optional seccomp) on Linux; native Windows in alpha [S] | Apache-2.0 [S] | Low overhead (no guest kernel), explicit grants for writes and network [S] | Host-kernel isolation only | **Strong candidate** (inside WSL2/Linux) |
| bubblewrap directly | Linux namespaces [K] | LGPL-2.0+ [K] | Minimal | Linux only | **Alternative** |
| Docker / Podman (rootless) | Containers; mature | Apache-2.0 [K] | Reproducible toolchains; service dependencies (DB) for integration tests | RAM overhead; Docker Desktop on Windows costs memory | **Use for integration tests that need services** |
| Docker Sandboxes (`sbx`) | microVM per agent [S] | Free with sign-in; runtime not OSS [S] | Strong isolation | Highest overhead (guest kernel + daemon) [S] | Unsuitable for 16 GB |
| NVIDIA OpenShell / microVMs | Emerging, alpha [S] | Apache-2.0 [S] | Strong isolation | Alpha; WSL2 experimental | Experimental |

**Security controls in the design** (p03, p12):
- Provenance tags on all untrusted text.
- Permissions enforced by the executor (path scope, network off, destructive commands go to HITL).
- Secrets read from the OS keychain by the Model Gateway only, never placed in prompts or the sandbox environment.
- Tool output truncated and stripped of control characters.
- Dependency installs as explicit, approved steps.
- Exact-pinned, hash-checked dependencies. The LiteLLM incident is the cautionary example: 1.82.7 and 1.82.8 exfiltrated credentials and secrets; 1.82.8 did so on every Python start via a `.pth` file [S].

### K. Observability and evaluation

| Technology | Role / maturity | Licence | Fit | Limits / hardware | Verdict |
|---|---|---|---|---|---|
| **Own event log (SQLite) + projections** | Core of the design | n/a | The group chat, dashboard, recovery and KPIs all read one log | You build the views | **Default** |
| OpenTelemetry GenAI conventions | Spec now maintained in a dedicated OTel GenAI repository; status to be checked [V/U] | Apache-2.0 | Standard span and attribute names for model calls, tools and agents; MCP now documents trace-context propagation [V] | Still evolving | **Adopt the naming**; export optional |
| [Arize Phoenix](https://www.morphllm.com/ai-agent-observability-tools) | Tracing/eval UI | **Elastic License 2.0** (source-available, not OSI) [S] | Single container, OTel-native | ELv2 restrictions on offering as a service | **Optional dev tool** |
| [Langfuse](https://www.morphllm.com/ai-agent-observability-tools) | LLM observability platform | MIT (thin enterprise folder) [S] | Mature UI, evals | Self-host needs ClickHouse + Redis + S3 [S]; too heavy next to a local model | **Exclude from MVP** |
| OpenLLMetry | OTel instrumentation | Apache-2.0 [S] | Auto-instrumentation | Overlaps with own gateway accounting | Optional |

**KPIs** (derived by Metrics, p10; all are stored per run, task and model):
- first-attempt pass rate
- final pass rate
- retries per verified task
- regression rate (tests that flipped from green)
- context tokens per attempt
- API tokens and cost per verified task
- local inference seconds per verified task
- HITL interventions per run
- recovery success (interrupted attempts that later verified)
- integration success per composite

### L. UI and group-chat visualisation

| Option | Fit | Limits | Verdict |
|---|---|---|---|
| **FastAPI backend + SSE (or WebSocket) + React/Svelte SPA** | Full control of the trace UI (run → task → attempt → step), cursor-based replay, decision cards | You build the components | **Default** |
| [AG-UI protocol](https://docs.copilotkit.ai/ag-ui) | An open event protocol for agent↔front-end streaming (CopilotKit-originated), with a Pydantic AI integration [V for existence] | Event model may not cover task-graph semantics; still evolving [U] | **Alternative**: map EventEnvelope to AG-UI if adopting CopilotKit components |
| Chainlit / Streamlit / Gradio | Fast prototypes | Chat-centric; poor fit for a task-tree trace and dashboard | Prototype only |

**Rule.** The UI renders *projections* of the event log, so internal events (`visibility=internal`) and user-visible messages are separated at the source, and ordering comes from `seq` per run.

### M. Document ingestion and normalisation

| Technology | Licence | Fit | Limits | Verdict |
|---|---|---|---|---|
| [Docling](https://www.danilchenko.dev/posts/markitdown-vs-docling-vs-marker/) | MIT [S] | Excellent tables including nested headers; automatic OCR of scanned regions; runs on CPU (CUDA optional) [S] | Slower: 41 s on a 14-page PDF on CPU in one test [S] | **Default for PDFs** |
| MarkItDown | MIT [S] | Very fast (0.6 s on the same file); good for DOCX/PPTX and clean digital PDFs [S] | Tables become run-on text; no OCR by default [S] | **Fast path for DOCX/MD and the first quality probe** |
| Marker | Code Apache-2.0 (v2+); **model weights under a modified OpenRAIL-M** licence (free below a revenue threshold) [S] | Good maths and figure extraction | Licence complexity for an open-source project | **Alternative**, licence review needed |
| PyMuPDF4LLM | AGPL-3.0 [K] | Fast | AGPL obligations | Exclude unless the project is AGPL-compatible |
| Tesseract OCR | Apache-2.0 [K] | Fallback OCR | Quality varies | Fallback |

**Pipeline** (p03): magic-byte type detection → primary extractor → quality metrics (text ratio, heading structure, table integrity, garbled-character rate) → up to 2 alternate extractors → section index with REQ anchors and per-section token counts. That index is what makes large documents usable by a small T1 model (map-reduce by section).

### N. Scheduling, resource management and cost control

| Responsibility | Deterministic or model? | Implementation |
|---|---|---|
| Inference concurrency (1–2 slots) | Deterministic | Local Runtime leases + llama.cpp `-np` slots [V]; `max_slots` from calibration |
| VRAM/RAM tracking | Deterministic | NVML (`nvidia-smi`/pynvml) [K] + OS counters; mark ESTIMATED when unavailable |
| Ready-set ordering | Deterministic | Critical path, unblock count, model affinity, age |
| API budgets and quotas | Deterministic | RunBudget counters in the State Store; Gateway checks before each call; circuit breakers |
| Provider failure handling | Deterministic | Exponential backoff + jitter, Retry-After, fallback chain |
| Leaf vs split | **Hybrid** | Deterministic estimates + T1 rubric + calibrated thresholds |
| How to split | Model (T3) | Validated deterministically |

**Model gateway libraries.** Prefer a **thin own gateway** over OpenAI-compatible HTTP (llama.cpp, Ollama and most providers speak it) plus one native SDK where needed. LiteLLM is an *alternative* for breadth of providers, but only with exact pins and hashes, given the March 2026 compromise [S].

### O. Architecture and interface documentation

| Technology | Fit | Verdict |
|---|---|---|
| **JSON Schema 2020-12** (generated from Pydantic models) | Same dialect MCP 2026-07-28 adopted for tool schemas [V]; one schema language for contracts, tools and events | **Default** |
| Python `Protocol` / typed stubs (`.pyi`) | "Signature-only views" for workers; checked by Pyright | **Default** for Python modules |
| OpenAPI 3.1 | HTTP module contracts; drives Schemathesis | When needed |
| TypeSpec / protobuf | Strong IDLs | Later / multi-language |
| ADR markdown files | Decision log | **Default** |

---

## Part 4 — Complete options compared (combinations)

| Stack | Components | Overlaps / redundancy | Difficulty | Assessment |
|---|---|---|---|---|
| **S1 Minimal-own (recommended)** | Python; own orchestrator on SQLite; Pydantic AI for typed calls; own thin gateway; llama.cpp server; own harness (mini-swe-agent design); git worktrees; srt/bubblewrap in WSL2; Docling + MarkItDown; FastAPI + SSE + React | None; each responsibility has one owner | Most code written by you, but every piece is small and testable | Best fit for the single-slot, contract-driven design |
| **S2 Durable-library** | S1 + **DBOS Transact** hosting the orchestrator's workflows and queues (SQLite) | DBOS queues overlap with the own scheduler. Use DBOS for durability and retries, and keep readiness/ranking in your code. | Lower recovery code; one more dependency and its decorators | Strong upgrade path once the PoC proves SQLite mode is adequate |
| **S3 LangGraph-centric** | LangGraph for orchestrator + inner loops, SQLite checkpointer; rest as S1 | The task graph inside LangGraph state duplicates the State Store; risk of two sources of truth | Re-executing interrupted nodes demands strict idempotency [S] | Viable, but less clean for a dynamic DAG with leases |
| **S4 Platform** | OpenHands SDK + Docker runtime + LiteLLM | Harness, sandbox and gateway all bundled | Heavy on 16 GB with Docker Desktop; designed for capable models | Good reference, poor fit for MVP |
| **S5 Enterprise durable** | Temporal + workers + Postgres | Overkill | Server footprint | Exclude |

**Better done in application code:** task-graph state, sizing, split validation, scheduling, budgets, context assembly, failure classification, event projections. **Better taken from libraries:** inference (llama.cpp), document parsing (Docling), testing/linting (pytest, Ruff, Pyright), VCS (git), sandbox (srt/bubblewrap), durable workflow plumbing (DBOS, optionally).

---

## Part 5 — New and experimental technologies worth investigating

| Candidate | Why it is interesting | Evidence | Risks | Label |
|---|---|---|---|---|
| Qwen3.6-35B-A3B at low-bit with expert offload | 3B active parameters; secondary sources describe strong agentic coding [S] | Apache-2.0 [S] | Q4 needs 14–24 GB [S]: likely exceeds your RAM + VRAM after the OS; low-bit quality loss | **Experimental**; test in E5 only on Linux |
| gpt-oss-20b with `--n-cpu-moe` | MoE fits "16 GB RAM" class [S]; llama.cpp supports expert offload [V] | Apache-2.0 [K] | Tight on Windows; not code-specific [S] | **Experimental → candidate** |
| DBOS Transact SQLite mode | Durable workflows without a server [V] | MIT [V] | Polling; Python step timeouts pending [V] | **PoC** |
| MCP 2026-07-28 stateless revision | Simpler servers; tasks extension; MRTR [V] | Linux Foundation governance [V] | SDKs catching up; deprecations | **Adopt for external tools, watch SDK maturity** |
| Agent Skills progressive disclosure | Keeps prompts small on a weak local model [V] | Open format [V] | Small models may not follow long skills; test | **Adopt format; measure** |
| `srt` native Windows (alpha) | Could avoid WSL2 [S] | Apache-2.0 [S] | Alpha | Experimental |
| AG-UI | Ready-made streaming UI components | Integrations exist [V] | Fit to task-graph trace unproven | Experimental |
| Calibrated, learnt leaf sizing (bandit-style threshold tuning) | Turns granularity into a measured control problem | Design proposal (this doc) | Needs enough runs | **Research track** inside E3 |

No core path depends on an experimental item. Each has a mature fallback: own state machine, dense 7–8B model, in-process tools, bubblewrap, FastAPI + SSE.

---

## Part 6 — Skills and tools by LLD location

Columns:
- **Det?** = should this be deterministic code? (Y = yes; H = hybrid; M = model)
- **Conf.** = confidence in the recommendation.

Skills listed are *capabilities to author*, not existing packages, unless a link is given.

| LLD submodule (page) | Responsibility | Det? | Recommended | Alternatives | Tools / protocols | Skill (capability) | Integration boundary | Key limitation | Conf. |
|---|---|---|---|---|---|---|---|---|---|
| M1 Project Input (p02) | Compose + upload | Y | React SPA + FastAPI upload | Svelte | HTTP multipart | — | IF-01 | Large files: chunked upload | High |
| M1 Group Chat (p02) | Trace view | Y | Event-log projection over SSE | AG-UI mapping | SSE / WebSocket | — | IF-18 | Virtualised rendering for long runs | High |
| M1 Decision Inbox (p02) | HITL cards | Y | Own components | CopilotKit | IF-03/04 | — | Broker API | — | High |
| M1 Dashboard (p02) | Metrics + controls | Y | Own charts | Grafana (heavier) | IF-19, IF-05 | — | Metrics API | Runtime metric gaps → ESTIMATED | High |
| M2 Intake Router (p03) | Idempotency, provenance | Y | Own code | — | — | — | IF-01 → stages | — | High |
| M2 Document Ingestion (p03) | PDF/DOCX → MD | Y | Docling + MarkItDown | Marker (licence review), Tesseract | CLI/library | — | Artifact Store | CPU time on big PDFs | High |
| M2 Repository Intake (p03) | Snapshot, detect, index, baseline | H | git + heuristics + tree-sitter + sandboxed test run; T1 proposes commands only if heuristics fail | Serena (GPL, via MCP) | git, ripgrep, tree-sitter, pytest | "detect-build-and-test-commands" | IF-15, IF-14 | Exotic build systems → HITL | Medium |
| M2 Prompt Normalisation (p03) | Structure brief | H | Deterministic normalise + T1 with JSON-schema constrained decoding (llama.cpp `--json-schema`) | Remote T3 if policy allows | IF-12 | "request-structuring" ([Agent Skills format](https://agentskills.io/)) | Gateway | Small models drop requirements → traceability check | Medium |
| M2 Request Understanding (p03) | Classify, clarify | H | Rules first; T1 tiebreak; checklist per type | — | IF-03 | "clarifying-questions" | Broker | Over-asking; batch questions | Medium |
| M3 Orchestrator / Run Control (p04) | Run lifecycle | Y | Own state machine (S1) | DBOS workflows (S2) | IF-05/06/16 | — | State Store | — | High |
| M3 Planning Agent (p04) | Design / diagnose / impact | M | T3 via Pydantic AI typed outputs; degraded T2 + approval | LangGraph inner loop | IF-12, IF-07 | "architecture-plan", "bug-diagnosis", "impact-analysis" | Registry | Remote quota | Medium |
| M3 Decomposition Engine (p05) | Size, split, validate, certify | H | Deterministic sizer + validator; T3 split proposals; T1 rubric | ADaPT-style executor-first mode as an experiment | IF-11/07/09/03 | "split-proposal" | State Store, Registry | Estimate accuracy → calibration | Medium (needs E2/E3) |
| M4 Scheduler (p07) | Readiness, ranking, leases | Y | Own code | DBOS queues | IF-13/09/20 | — | Local Runtime | — | High |
| M4 Coding Worker (p07) | Implement leaf | M | Own harness on llama.cpp (T2) | Aider; mini-swe-agent baseline; OpenHands SDK | IF-11/12/14/15 | "python-module-from-contract", "tests-from-acceptance" | Tool Executor | Small-model tool-call reliability | Medium |
| M4 Verification Gate (p08) | Gates + classification | Y (+ optional M reviewer) | pytest, Ruff, Pyright, Hypothesis; rule-based log classifier | Reviewer T3 | IF-14/15/07 | "review-diff-against-contract" (reviewer only) | Workspace, Registry | Flaky tests | High |
| M4 Integration & Repair (p08) | Bottom-up integration | Y + M (repair leaf) | Own code + targeted repair leaves | — | IF-09/10 | "repair-from-failing-tests" | Scheduler | Localisation accuracy | Medium |
| M5 Registry (p09) | Versioned contracts | Y | Pydantic → JSON Schema 2020-12; Python stubs; semver rules | OpenAPI, TypeSpec | IF-07/08 | — | State Store | Semantic compatibility beyond signatures | Medium |
| M5 State Store (p09) | Transactions, outbox, recovery | Y | SQLite WAL | Postgres; DBOS system DB | IF-16/24 | — | all | Single writer | High |
| M5 Artifact & Workspace (p09) | VCS + blobs | Y | git worktrees + CAS folder | — | IF-15 | — | Tool Executor | Disk use → GC | High |
| M5 Event Stream (p10) | Append, fan-out, replay | Y | SQLite table + in-process pub/sub + SSE | NATS (later) | IF-17/18 | — | UI, Metrics | — | High |
| M5 Decision Broker (p10) | Durable HITL | Y | Own code | LangGraph interrupt (inner loops) | IF-03/04 | — | UI | — | High |
| M5 Metrics (p10) | KPIs, advisories | Y | Own aggregation; OTel naming | Phoenix (ELv2) for dev | IF-19/20 | — | Dashboard | Measured vs estimated | High |
| M5 Model Gateway (p11) | Routing, retries, schema, usage | Y | Own thin gateway (OpenAI-compatible + native SDKs) + Pydantic AI | LiteLLM (pinned, hashed) | IF-12 | — | Providers | Provider API drift | Medium |
| M5 Local Runtime (p11) | Leases, residency, calibration | Y | llama.cpp server + own lease manager; NVML probes | Ollama | IF-13/20 | — | Gateway, Scheduler | Windows memory overhead | Medium |
| M5 Tools & Skills / Executor (p12) | Registry, permissions, sandbox | Y | Agent Skills folders; in-process tools; MCP for external; `srt`/bubblewrap | Docker | IF-14/23 | — | Workspace | Windows-native sandbox maturity | Medium |
| M5 Context & Memory (p12) | Budgeted packs, memory upkeep | Y (+ T1 summaries) | tree-sitter repo map + ripgrep + registry signatures; model tokenizer counts | Serena (MCP), embeddings later | IF-11 | — | Registry, Workspace | Tokenizer mismatch across models | Medium |

---

## Part 7 — Recommended MVP stack

| Layer | Default | Credible alternative | Why (hardware, budget, architecture) |
|---|---|---|---|
| Language | Python 3.12+ | TypeScript | Best ecosystem for parsing, testing and local inference clients |
| Orchestration / durability | Own state machine on SQLite | DBOS Transact (SQLite) | One source of truth for the task DAG; no server processes |
| Typed model calls | Pydantic AI | Direct SDK calls | Schema-validated outputs; model-agnostic |
| Model gateway | Own thin gateway | LiteLLM (pinned + hashed) | Small attack surface; OpenAI-compatible everywhere |
| Local runtime | llama.cpp `llama-server` | Ollama | JSON-schema decoding, MoE offload, KV quantisation, slots, metrics [V] |
| T2 coder | Winner of E5 among Qwen3-8B, Qwen2.5-Coder-7B, gpt-oss-20b | Qwen3.6-35B-A3B low-bit (experimental) | Must fit 6 GB VRAM (+ offload) with measured C_eff |
| T1 helper | Same model as T2 | Qwen3-1.7B/4B if both stay resident | Avoids model-swap thrash on one slot |
| T3 planner | 1 paid + 1 free provider, chosen after E9 | Local degraded mode | Quota uncertainty |
| Harness | Own minimal harness | Aider / mini-swe-agent | Policy hooks; small models |
| Tools / skills | In-process JSON-Schema tools; Agent Skills format; MCP for external servers | — | Progressive disclosure; open standards |
| Context | tree-sitter + ripgrep + registry signatures | Serena via MCP (GPL caution) | Deterministic, cheap |
| State / artifacts | SQLite WAL + git worktrees + CAS folder | Postgres later | Local-first, easy backup |
| Verification | pytest, Ruff, Pyright, Hypothesis | mypy; Schemathesis for APIs | Deterministic gates |
| Sandbox | WSL2/Linux + `srt` (bubblewrap) | Rootless Docker/Podman | Low overhead on 16 GB |
| Observability | Own event log + OTel GenAI naming | Phoenix for dev | No heavy services |
| UI | FastAPI + SSE + React | AG-UI / CopilotKit components | Custom trace UI needed |
| Ingestion | Docling + MarkItDown | Marker (licence review) | Tables and OCR on CPU |

**Replaceability boundaries** (keep these as interfaces in code):

| Interface | What can be swapped behind it |
|---|---|
| IF-12 `InferenceRequest` | Any provider or runtime |
| IF-13 `SlotLease` | Any local runtime |
| IF-14 `ToolInvocation` | Any sandbox |
| IF-11 `ContextPack` | Any retrieval method |
| IF-16/17 `StateCommit` / `EventPublish` | Any store or bus |
| IF-07/08 `Contract*` | Any IDL |

**Decide now:** T-1 language, T-2 "own state machine first", T-3 runtime, T-8/T-9 OS and sandbox, D1 approval policy.
**Keep open until benchmarks:** T-4 model, T-5 provider, DBOS adoption, the reviewer default, budgets (D2).
**PoC before adoption:** DBOS SQLite mode; gpt-oss-20b offload on your machine; Docling throughput on your documents; `srt` inside WSL2.
**Excluded from MVP, and why:**

| Excluded | Reason |
|---|---|
| Temporal | Server and DB footprint. |
| vLLM / SGLang | No gain at one slot on 6 GB; Linux/CUDA-first. |
| Langfuse self-host | ClickHouse + Redis + S3 is too heavy. |
| Docker Sandboxes (sbx) | microVM overhead. |
| Embedding search | No demonstrated need; extra RAM. |
| Multi-agent frameworks as the core | Conversation-centric, parallel-agent assumptions. |
| PyMuPDF4LLM | AGPL. |
| Qwen3-Coder-Next | ~46 GB at 4-bit. |

---

## Part 8 — How the design makes granularity decisions without relying entirely on an LLM

1. **Measured model profile (calibration job, p11).** For each local model and runtime setting, measure tokens per second, VRAM per context length, the largest usable context, and **pass rate by task-size bucket** on a fixed calibration set. C_eff is the largest context at which the pass rate stays above target.
2. **Deterministic size estimate (p05).**
   - est_in = spec + pinned signatures + allowed files + top-k snippets + tool schemas, counted with the model's tokenizer.
   - est_out = k × functions to write + test code, with k learnt from history.
   - Plus the counts of files, interfaces and acceptance criteria.
3. **One cheap rubric call (T1)** scores ambiguity and coupling on a bounded scale. This is the only model judgement in the leaf decision.
4. **Threshold test** against the profile (default est ≤ 0.6·C_eff, files ≤ 3, interfaces ≤ 4, risk ≤ R).
5. **Dry-run context assembly** before certification. CONTEXT_OVERFLOW forces a split.
6. **Feedback.** SPEC_TOO_LARGE failures and first-pass rates update the success table, and thresholds tighten or relax slowly (E3).

---

## Part 9 — Experimental evaluation plan (on your hardware)

### 9.1 Benchmark corpus (university-level; author hidden tests *before* any run)

| ID | Project | Size target | Why |
|---|---|---|---|
| P1 | CLI task manager with JSON/SQLite persistence | ~600 LOC | Simple modules, clear contracts |
| P2 | REST API (FastAPI) for a library system: books, members, loans, auth | ~1.5k LOC | Layered modules; HTTP contracts; integration tests |
| P3 | Game-logic engine (e.g. 2048 or tic-tac-toe AI with minimax) + CLI | ~800 LOC | Algorithmic leaves; property tests |
| P4 | Data pipeline: CSV ingest → validate → aggregate → report | ~1k LOC | Linear dependencies; deterministic outputs |
| P5 | Event-sourced inventory service with a small web UI | ~2.5k LOC | Deep decomposition; stress test for recursion |

| Task type | Count | How produced |
|---|---|---|
| **Debug** | 20 | Seeded faults (off-by-one, wrong condition, missing null check, contract drift) injected into finished P1–P4, each with a failing hidden test |
| **Feature** | 15 | e.g. "add overdue fines to P2", "undo in P3", "CSV export in P4" |
| **Integration** | 10 | Two modules built separately against contracts, then integrated, with seeded interface mismatches |
| **Refactor** | 5 | Behaviour-preserving restructures with characterisation tests |

### 9.2 Experiments

| ID | Question | Design | Primary metrics |
|---|---|---|---|
| **E1** Calibration | What fits and how fast? | Each candidate model × runtime × KV-cache type × context {4K, 8K, 16K, 32K}; Windows vs WSL2 | VRAM/RAM peak, tok/s prompt + generation, OOM boundary, C_eff from a 40-task calibration set |
| **E2** Decomposition ablation (core) | Does recursive, contract-driven decomposition beat alternatives **with one slot**? | Same T2 model, same budget, P1–P5 under five arms: (a) no decomposition; (b) one-level plan; (c) fixed depth 2; (d) **recursive sizing (this design)**; (e) ADaPT-style executor-first | Final pass rate (hidden tests), first-pass rate, total local inference s, API tokens, # leaves, # re-splits, integration failures, wall-clock |
| **E3** Leaf threshold sweep | Where is the sweet spot? | Arm (d) with thresholds 0.4 / 0.6 / 0.8 · C_eff and F_max 2/3/5 | Pass rate vs leaves vs time; over- and under-decomposition counts |
| **E4** Context strategy | What should a leaf see? | Full dependency files vs signature-only vs signature + repo-map vs + embeddings | Pass rate, context tokens, regression rate |
| **E5** T2 model choice | Which local coder? | Winner configs from E1 on E2 arm (d) | Pass rate per hour, cost per verified task |
| **E6** Runtime choice | llama.cpp vs Ollama | Same model and quantisation | Throughput, schema-valid output rate, memory, stability over a 4-hour run |
| **E7** Verification policy | Is a reviewer worth it? | Deterministic only vs + reviewer on policy-selected diffs | Escaped defects (hidden tests), false blocks, API cost |
| **E8** Recovery | Does resume work? | Kill the process / reboot at random points (30 injections over P2, P5) | Recovered without redoing VERIFIED work, time to resume, corrupted states (target 0) |
| **E9** Remote tier value | When is T3 worth paying for? | Planning + splitting by T3 vs local T2 (degraded mode) | Pass rate, HITL count, API cost per verified task, quota events |
| **E10** Single vs dual slot | Does a 2nd slot help or hurt? | `max_slots` 1 vs 2 where E1 says it fits | Throughput, OOM/thrash events, pass rate |

### 9.3 Fairness and validity rules

- **Fix the inputs.** Same specs, same hidden tests, same seeds, temperature 0 (or a fixed seed), same wall-clock and token budgets per arm.
- **Repeat.** Run each configuration 3 times; report the mean and a 95% bootstrap CI; use a paired comparison per task.
- **Hide the tests.** Hidden tests are never in any context pack. Visible acceptance tests are generated by the system, so verification is not graded by its own tests.
- **Log everything.** Exact model file hash, quantisation, runtime version, flags, OS, driver.
- **Count humans.** HITL answers come from a fixed answer script so runs are comparable; count interventions.
- **Benchmarks are context, not evidence.** Vendor and public benchmarks (SWE-bench etc.) can motivate choices but never replace E2/E5 on your machine.
- **Measure test strength.** Run mutation testing (mutmut) on the *generated* test suites to measure their strength; a high pass rate with weak tests is a false positive.

### 9.4 Success criteria for the MVP (proposed)

- **E2:** arm (d) beats (a) and (c) on final pass rate for P2–P5 with non-overlapping CIs, using ≤ 1.5× their local inference time.
- **E8:** 100% of injections recover; 0 VERIFIED tasks re-executed; 0 corrupted states.
- **E4:** signature-only context is within 5 points of full-file context at ≤ 50% of the tokens.

---

## Part 10 — Sources

**Orchestration / durability**
- DBOS Transact Python repository (MIT, Postgres, queues, resume): https://github.com/DBOS-project/dbos-transact-py
- DBOS configuration reference (SQLite system database): https://docs.dbos.dev/python/reference/configuration
- What's new in DBOS, July 2026: https://dbos.dev/blog/new-in-dbos-july-2026
- Pydantic AI durable execution overview: https://pydantic.dev/docs/ai/integrations/durable_execution/overview/
- DBOS + Pydantic AI: https://docs.dbos.dev/integrations/pydantic-ai
- Temporal + Pydantic AI: https://temporal.io/blog/build-durable-ai-agents-pydantic-ai-and-temporal
- LangGraph 2026 changes (versions, interrupts, RunControl): https://www.developersdigest.tech/blog/langchain-langgraph-whats-new-2026
- Temporal vs Restate vs Windmill (licences, footprint): https://www.pkgpulse.com/guides/temporal-vs-restate-vs-windmill-durable-workflow-2026

**Harnesses**
- mini-swe-agent: https://github.com/SWE-agent/mini-swe-agent
- OpenHands overview (licences, SDK, sandbox): https://rywalker.com/research/openhands
- OpenHands Software Agent SDK (MLSys 2026): https://proceedings.mlsys.org/paper_files/paper/2026/hash/8ae9cf363ea625161f885b798c1f1f78-Abstract-Conference.html
- Harness Engineering: a source-code study of eleven coding agents: https://arxiv.org/pdf/2609.00006
- Aider overview: https://botmonster.com/ai/aider-model-agnostic-ai-pair-programmer/

**Planning research**
- ADaPT: As-Needed Decomposition and Planning with Language Models: https://arxiv.org/html/2311.05772v2

**Models and runtimes**
- llama.cpp server README (flags): https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- Ollama repository: https://github.com/ollama/ollama
- Best Ollama models by VRAM (Oct 2026): https://www.morphllm.com/best-ollama-models
- Best local LLM by RAM tier (Sep 2026): https://klymentiev.com/blog/best-local-llm
- Qwen3-Coder-Next local requirements: https://unsloth.ai/docs/models/qwen3-coder-next
- Qwen3.6 explained (sizes, licence): https://www.layer3labs.io/guides/qwen-3-6-explained
- Gemini API pricing/free-tier changes (aggregator; verify in AI Studio): https://agentdeals.dev/gemini-api-pricing-changes

**Protocols and skills**
- MCP 2026-07-28 changelog: https://modelcontextprotocol.io/specification/2026-07-28/changelog
- MCP release listing: https://releases.sh/modelcontextprotocol/mcp-specification.md
- MCP at the Agentic AI Foundation: https://aaif.io/projects/model-context-protocol
- Agent Skills: https://agentskills.io/
- AG-UI protocol: https://docs.copilotkit.ai/ag-ui

**Context**
- Serena (licence split): https://github.com/oraios/serena

**Documents**
- MarkItDown vs Docling vs Marker (Aug 2026): https://www.danilchenko.dev/posts/markitdown-vs-docling-vs-marker/

**Security and sandboxing**
- Local agent sandboxes compared: https://rywalker.com/research/local-agent-sandboxes
- LiteLLM supply-chain attack analysis: https://www.comet.com/site/blog/litellm-supply-chain-attack/

**Observability**
- AI agent observability tools (licences, acquisitions): https://www.morphllm.com/ai-agent-observability-tools
- OpenTelemetry GenAI semantic conventions (moved to a dedicated repo): https://opentelemetry.io/docs/specs/semconv/gen-ai/

*Items marked [K] are standard, long-established facts (e.g. SQLite public domain, pytest MIT) and were not re-fetched. Items marked [U] should be confirmed before any decision depends on them.*
