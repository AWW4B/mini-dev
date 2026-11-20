# FILE: src/asf/m5_shared/stack.py
# ROLE: The project's tech stack contract: one decision (language, libraries, CLI and test framework, layout) every agent follows and the gate enforces.
# ARCH REF: M5 shared; D-01 deterministic-first (the stack is derived by code from the spec, never chosen per task by a model)
# OWNS: StackContract, its derivation from the spec text, .factory/stack.json, the import check
# DOES NOT OWN: Running the gate (m4 verification), prompts (each agent adds stack_prompt to its own)
# CONNECTS TO (external boundaries only):
#   - reads and writes <project>/.factory/stack.json
#   - called by src/asf/m3_orchestration/run_graph.py: derive_stack, save_stack
#   - called by src/asf/m4_execution/verification/gate.py: find_stack, foreign_imports
#   - called by src/asf/m4_execution/worker/strategies.py: find_stack, stack_prompt
#   - called by src/asf/m3_orchestration/planning/test_authoring.py: find_stack, stack_prompt
#   - called by tests/m5_shared/test_stack.py: StackContract, derive_stack, save_stack, find_stack, stack_prompt, foreign_imports
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Deterministic: the same spec gives the same stack; a library is allowed only when the spec names it.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/test_stack.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/stack.py` and `uv run mypy src/asf/m5_shared/stack.py` are clean.

import ast
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# libraries a spec may name; anything else stays out unless a person adds it to .factory/stack.json
_KNOWN = {
    "click": "cli", "typer": "cli", "argparse": "cli", "rich": "lib", "requests": "lib", "httpx": "lib", "flask": "lib", "fastapi": "lib",
    "pydantic": "lib", "numpy": "lib", "pandas": "lib", "pyyaml": "lib", "sqlalchemy": "lib",
}
_IMPORT_NAME = {"pyyaml": "yaml"}
_TEST_ONLY = {"pytest"}


@dataclass
class StackContract:
    language: str = "python"
    python: str = f"{sys.version_info.major}.{sys.version_info.minor}"
    cli: str = "argparse"
    tests: str = "pytest"
    layout: str = "src"
    libraries: list[str] = field(default_factory=list)  # third-party imports allowed in source files (stdlib is always allowed)


def derive_stack(spec_text: str) -> StackContract:
    """The stack the spec asks for: stdlib only unless it names a library; the CLI library it names, else argparse."""
    words = set(re.findall(r"[a-z][a-z0-9_-]+", spec_text.lower()))
    named = sorted(name for name in _KNOWN if name in words)
    cli = next((name for name in named if _KNOWN[name] == "cli"), "argparse")
    libraries = [_IMPORT_NAME.get(n, n) for n in named if n != "argparse"]
    return StackContract(cli=cli, libraries=libraries, layout="src" if "src/" in spec_text else "flat")


def save_stack(project_root: Path, contract: StackContract) -> Path:
    target = project_root / ".factory" / "stack.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():  # a person's edit of the file wins over a re-derivation
        target.write_text(json.dumps(asdict(contract), indent=2), encoding="utf-8")
    return target


def find_stack(start: Path) -> StackContract | None:
    """The contract of the project that holds ``start`` (a worktree lives under <project>/.worktrees/<task>)."""
    for folder in (start, *start.parents):
        path = folder / ".factory" / "stack.json"
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            return StackContract(**{k: v for k, v in data.items() if k in StackContract.__dataclass_fields__})
    return None


def stack_prompt(contract: StackContract | None) -> str:
    if contract is None:
        return ""
    libs = ", ".join(contract.libraries) or "none (standard library only)"
    return (
        f"TECH STACK (binding for every task, decided once for the whole project): {contract.language} {contract.python}; "
        f"third-party libraries allowed: {libs}; command line parsing: {contract.cli}; tests: {contract.tests}; "
        f"layout: {'src/<package>/' if contract.layout == 'src' else 'flat'}. Do not use any other library or framework."
    )


def foreign_imports(source: str, contract: StackContract, project_packages: set[str], *, is_test: bool = False) -> list[str]:
    """Top-level modules a file imports that are neither stdlib, the project's own, nor allowed by the contract."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # the lint gate reports syntax errors
    allowed = set(sys.stdlib_module_names) | project_packages | set(contract.libraries) | ({contract.cli, contract.tests, *_TEST_ONLY} if is_test else {contract.cli})
    found: list[str] = []
    for node in ast.walk(tree):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) and node.module and node.level == 0 else []
        for name in names:
            top = name.split(".")[0]
            if top not in allowed and top not in found:
                found.append(top)
    return found
