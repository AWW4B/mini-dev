# FILE: src/asf/m2_request/prompt_normalisation.py
# ROLE: Normalises the user prompt (cleanup, language, explicit constraints) before understanding; deterministic first, T1 optional.
# ARCH REF: M2; p03 Prompt Normalisation & Optimisation
# OWNS: Normalised prompt text
# DOES NOT OWN: Requirement extraction
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (IF-12 model calls)
#   - called by src/asf/m2_request/pipeline.py: normalise_prompt
#   - called by tests/m2_request/test_prompt_normalisation.py: normalise_prompt
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m2_request/test_prompt_normalisation.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m2_request/prompt_normalisation.py` and `uv run mypy src/asf/m2_request/prompt_normalisation.py` are clean.

def normalise_prompt(text: str) -> str:
    raise NotImplementedError
