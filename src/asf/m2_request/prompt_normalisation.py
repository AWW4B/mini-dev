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

import re
from typing import Any, cast

from asf.m5_shared.gateway.gateway import ModelGateway

_UNICODE_REPLACEMENTS = {
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u2014": "--",
    "\u2013": "-",
    "\u00a0": " ",
}


def _clean_deterministic(text: str) -> str:
    cleaned = text
    for old, new in _UNICODE_REPLACEMENTS.items():
        cleaned = cleaned.replace(old, new)

    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

    lines = []
    for line in cleaned.splitlines():
        line_stripped = line.rstrip()
        # Normalize list markers * or + at start of line to -
        m = re.match(r"^(\s*)[*+](\s+.*)$", line_stripped)
        if m:
            line_stripped = f"{m.group(1)}-{m.group(2)}"
        lines.append(line_stripped)

    # Collapse multiple consecutive blank lines
    result_lines: list[str] = []
    blank_count = 0
    for l_text in lines:
        if not l_text.strip():
            blank_count += 1
            if blank_count <= 1:
                result_lines.append("")
        else:
            blank_count = 0
            result_lines.append(l_text)

    return "\n".join(result_lines).strip()


def normalise_prompt(text: str, gateway: ModelGateway | None = None) -> str:
    deterministic = _clean_deterministic(text)
    if not deterministic:
        return ""

    if gateway is not None:
        try:
            model = gateway.model_for(cast(Any, "T1"), purpose="normalisation")
            resp = model.invoke(
                f"Clean up and optimize the following prompt for software development tasks. "
                f"Keep all user constraints, remove ambiguity, and output only the normalized prompt:\n\n{deterministic}"
            )
            content = getattr(resp, "content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
            return str(resp).strip()
        except Exception as _err:  # noqa: BLE001
            _ = _err
            return deterministic

    return deterministic
