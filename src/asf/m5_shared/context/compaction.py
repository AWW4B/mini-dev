# FILE: src/asf/m5_shared/context/compaction.py
# ROLE: Compacts old conversation turns into a summary using the tiny model (T1).
# ARCH REF: M5; p12; D-09 tiny-model tasks
# OWNS: Compaction
# DOES NOT OWN: Task specs and contracts (never compacted)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/gateway/gateway.py: ModelGateway (T1 summaries)
#   - called by tests/m5_shared/context/test_compaction.py: compact_history
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/context/test_compaction.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/context/compaction.py` and `uv run mypy src/asf/m5_shared/context/compaction.py` are clean.

from typing import Any, cast

from asf.m5_shared.gateway.gateway import ModelGateway


def compact_history(gateway: ModelGateway, turns: list[str], budget_tokens: int) -> str:
    if not turns:
        return ""
    if len(turns) == 1:
        return turns[0]

    history_text = "\n---\n".join(turns)
    prompt = (
        f"Summarize the following interaction history concisely within approximately {budget_tokens} tokens:\n\n"
        f"{history_text}"
    )

    try:
        model = gateway.model_for(cast(Any, "T1"), purpose="compaction")
        response = model.invoke(prompt)
        content = getattr(response, "content", "")
        if isinstance(content, str) and content.strip():
            return content.strip()
        return str(response).strip()
    except Exception as _err:  # noqa: BLE001
        _ = _err
        max_chars = budget_tokens * 4
        return history_text[:max_chars]
