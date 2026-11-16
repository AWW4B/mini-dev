# Model shortlist for mini-dev (desk research, 2026-11-16)

Status: DRAFT. Numbers come from blog roundups, not model cards, and are mostly unverified. Check each model card or provider page before copying a number into `models.toml`. No behaviour tests have been run.

## T2: local coder (6 GB VRAM / 16 GB RAM)

| Model | Quant / VRAM | Context (native) | Tool calling | Benchmarks found | Notes |
|---|---|---|---|---|---|
| Qwen2.5-Coder-7B-Instruct | Q4_K_M, about 5 GB | 128K (usable context at this size is far smaller) | Weak or prompt-based | HumanEval is the best of the 7-8B class, per one blog. No SWE-bench or LiveCodeBench found. | Guides name it the best fit for 6 GB. Safe default. |
| Qwen3.5-9B (Ollama `qwen3.5:9b`) | Q4, about 6.6 GB | Not verified | Not verified | Not verified | Borderline on 6 GB. Offload some layers to CPU. |
| Qwen2.5-Coder-3B / 1.5B | about 2 GB / 1 GB | 32K | Weak | Not verified | Fallback or autocomplete only. |
| Qwen3-Coder-30B-A3B | about 19 GB | 256K | Yes (native, per the SGLang cookbook) | Strongest SWE-bench of the family | Does NOT fit 6 GB VRAM. Only usable with heavy CPU offload, and slow. Listed in `models.toml` as a suggestion. |

## T3: free-API planner/reviewer (reasoning and large context)

| Provider | Context | Free limits (approximate, they change) | Caveats |
|---|---|---|---|
| Google Gemini (Flash / Flash-Lite) | 1M | Flash about 10 RPM, Flash-Lite about 15 RPM. Pro is paid-only since April 2026. | Free-tier data may be used for training. Limits were cut in 2026. |
| OpenRouter `:free` models | Varies, up to 1M on some | 20 RPM, 50 requests/day (1,000/day after a $10 top-up) | Model IDs expire, so keep a fallback chain. |
| Groq (Llama 3.3 70B, gpt-oss-120b) | 131K on gpt-oss-120b | About 30 RPM | Very fast. No credit card needed. |
| Cerebras | Not verified | About 1M tokens/day | High volume. |
| Mistral | Not verified | About 2 RPM, 1B tokens/month | Free use requires opting in to data training. |

Suggested chain: Gemini Flash (primary, largest context), then Groq gpt-oss-120b, then OpenRouter free, then Cerebras. It matches the repo's fallback-chain design, but this is untested.

## T1: CPU-only helper (RAM only)

| Model | Context | CPU speed (Ollama, one test) | Notes |
|---|---|---|---|
| Qwen3-1.7B | 32K | Not measured. Qwen3-0.6B ran at about 35 tok/s. | The repo's suggestion. Fine for rubric scoring and summaries. |
| Qwen3-4B | 32K | Not measured | Better quality, slower on CPU. |
| Gemma 3 4B | 128K (degrades past about 64K) | Not measured | |
| Phi-4-mini 3.8B | 128K | About 6.9 tok/s | Slow on CPU. |

Open question for Awwab: does "it will only perform tests" mean the CPU model runs the benchmarks, or that it writes tests? The repo requires T3 to author acceptance tests (rule A-4), so it can't be the second.

## Not found
- Tool-calling benchmarks (for example BFCL) for any of the small models.
- SWE-bench and LiveCodeBench numbers for models that fit in 6 GB.
- Verified free-tier context windows for Cerebras and Mistral.

## Behaviour tests still to run (Awwab's second ask)
1. Planner: give a Gemini or Groq model 3-5 sample goals, then check that the splits fit within 0.6 x C_eff and the acceptance tests are sensible.
2. Worker: give Qwen2.5-Coder-7B the resulting leaf tasks, then check whether the code passes the acceptance tests. Run `uv run factory models test` once `models.toml` is filled in.

## Sources
- https://www.sitepoint.com/best-local-llm-models-2026/
- https://localaimaster.com/vram/best-coding-llm-6gb-vram
- https://docs.sglang.io/cookbook/autoregressive/Qwen/Qwen3-Coder
- https://openrouter.ai/blog/tutorials/free-llm-apis-compared/
- https://agentdeals.dev/gemini-api-pricing-changes
- https://wetheflywheel.com/en/ai-model-access/free-llm-api-tiers-2026/
- https://www.popularai.org/p/best-cpu-only-local-llm-2026
- https://blog.premai.io/best-lightweight-language-models-worth-running
