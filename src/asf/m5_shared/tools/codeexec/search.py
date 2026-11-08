# FILE: src/asf/m5_shared/tools/codeexec/search.py
# ROLE: Implements search_tools(query, detail): searchable view of the tools a role may call.
# ARCH REF: M5; p12; D-19; D-19a
# OWNS: Tool search
# DOES NOT OWN: Policy (still enforced by the executor at call time)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/tools/registry.py: ToolRegistry (source of truth)
#   - called by tests/m5_shared/tools/codeexec/test_search.py: search_tools
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/tools/codeexec/test_search.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/tools/codeexec/search.py` and `uv run mypy src/asf/m5_shared/tools/codeexec/search.py` are clean.

from typing import Any, Literal

from asf.m5_shared.tools.registry import ToolRegistry


def search_tools(
    registry: ToolRegistry,
    role: str,
    query: str,
    detail: Literal["names", "descriptions", "full"] = "names",
) -> list[dict[str, Any]]:
    specs = registry.specs_for(role)
    q = query.strip().lower()

    matched = []
    for spec in specs:
        if not q or q == "*":
            matched.append(spec)
        elif (
            q in spec.name.lower()
            or q in spec.description.lower()
            or q in getattr(spec, "source", "").lower()
        ):
            matched.append(spec)

    results: list[dict[str, Any]] = []
    for s in matched:
        if detail == "names":
            results.append({"name": s.name})
        elif detail == "descriptions":
            results.append({"name": s.name, "description": s.description})
        else:  # "full"
            results.append({
                "name": s.name,
                "description": s.description,
                "args_schema": getattr(s, "args_schema", {}),
                "destructive": getattr(s, "destructive", False),
                "needs_network": getattr(s, "needs_network", False),
                "roles": getattr(s, "roles", []),
                "source": getattr(s, "source", ""),
            })

    return results
