# First real run: findings (wordfreq mini project)

A small spec (`wordfreq`, a word-frequency CLI) was run through the factory with the real models: T1 Qwen3-1.7B on CPU, T2
Qwen2.5-Coder-7B on the GPU (both started by `LlamaServerBackend`), T3 and reviewer on Groq (`openai/gpt-oss-120b`, `gpt-oss-20b`),
Gemini as the last fallback, five Groq keys rotating. The detailed per-step log of the last run is `RUN_REPORT.txt` in the demo project.

## Fixed (each on its own branch, merged to local main, with a test)
1. `--file` attachments reached the planner as an empty request (blob refs were never read back).
2. The tiny model's prompt rewrite added chatter that became requirements; it is now trusted only if it keeps every `code` token.
3. `--mode` was ignored in favour of a keyword guess.
4. The tiny model's rubric stalled runs (ambiguity 1.0, coupling 0.8-0.95 for simple tasks); its scores are now bounded by a heuristic.
5. Test authoring: a dict keyed by path made the planner model return the module under test; it now returns a list of {path, content};
   it re-asks twice on bad paths instead of aborting; names the test files; skips files that already are tests.
6. Strict `json_schema` refusals fall back to tool calling; a 429 moves to the next key at once; remote calls time out after 60 s.
7. `run resume` ignored `active_profile` (it used "hybrid").
8. The 7B coder answers `{"action": "write_file", ...}`; read as a tool call. `done` is refused until the acceptance tests ran; the
   acceptance test source is put in the prompt.
9. `factory tasks show` crashed on a non-breaking hyphen (Windows code page); the CLI writes UTF-8.
10. The run recorded no planner/decomposer/worker events, so the web viewer was empty; the run now narrates paired hand-offs.
11. Queued leaf specs are saved to `.factory/specs` and re-queued by `run resume` (the scheduler queue was in memory only).
12. Groq first for the planner (Gemini took 20-110 s per call); Gemini model name updated.

## Open (found, not fixed)
- **A resolved `manual_split` or `clarify` decision from the decomposer is never applied.** `accept_larger_leaf` leaves the node ESCALATED
  and the run waits forever; only the escalation handler's own manual_split path is consumed. Needs: on resume, apply the answer
  (accept -> certify the node as a leaf, abandon -> ABANDONED, clarified -> back to sizing).
- **Task detail is lost between spec and worker.** The worker sees "Provide core functionality for word frequency analysis" and the
  acceptance test source, but not `top_words(text, n)`: capsules are empty and the requirement lines do not reach the leaf. The 7B then
  invents names. Pin the requirement text (or signatures) into the leaf spec or the semantic memory layer.
- The 7B coder through the JSON tool protocol is weak (triple-quoted JSON strings, invented names). Consider `whole_file_edit`, a larger
  local model, or escalating a failed leaf to the planner tier once.
- `call_metrics` stays empty and `budget.used_local_tokens` stays 0 after real calls.
- First call to each provider took 15-70 s (cause not found; possibly IPv6 fallback).
- Both llama-servers write one shared `llama-server.log` (interleaved).
- A second `run resume` running at the same time produced "database is locked" in the broker.
- The planner's opening events are narrated twice after a resume (the node re-runs).
- The run process exits at the first human decision; unattended runs need a driver that answers decisions (the autopilot script used here
  was a scratch file, not in the repo).
