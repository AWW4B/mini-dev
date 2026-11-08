# FILE: src/asf/m5_shared/tools/codeexec/facade_gen.py
# ROLE: Generates the typed Python facade module that scripts import; every facade function sends a framed request to the parent.
# ARCH REF: M5; p12; D-19a
# OWNS: Facade source generation
# DOES NOT OWN: Executing calls
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/tools.py: ToolSpec (specs)
#   - called by src/asf/m5_shared/tools/codeexec/runner.py: generate_facade
#   - called by tests/m5_shared/tools/codeexec/test_facade_gen.py: generate_facade
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/tools/codeexec/test_facade_gen.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/tools/codeexec/facade_gen.py` and `uv run mypy src/asf/m5_shared/tools/codeexec/facade_gen.py` are clean.

from asf.contracts.tools import ToolSpec

_TYPE_MAP = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "list[Any]",
    "object": "dict[str, Any]",
}


def _map_type(prop_info: dict[str, str]) -> str:
    raw_type = prop_info.get("type", "any")
    return _TYPE_MAP.get(raw_type, "Any")


def generate_facade(specs: list[ToolSpec]) -> str:
    """Return Python source for module 'tools' with one typed function per spec."""
    lines: list[str] = [
        '"""Generated typed tools facade for code execution sandbox."""',
        "import os",
        "import sys",
        "import json",
        "import uuid",
        "from typing import Any",
        "",
        '_TAG = os.environ.get("ASF_EXEC_TAG", "")',
        '_FD_IN = int(os.environ.get("ASF_EXEC_FD_IN", "3"))',
        '_FD_OUT = int(os.environ.get("ASF_EXEC_FD_OUT", "4"))',
        "",
        "_channel = None",
        "",
        "def _get_channel() -> Any:",
        "    global _channel",
        "    if _channel is None:",
        "        try:",
        '            r = os.fdopen(_FD_IN, "rb", buffering=0)',
        '            w = os.fdopen(_FD_OUT, "wb", buffering=0)',
        "            from asf.m5_shared.tools.codeexec.channel import FramedChannel",
        "            _channel = FramedChannel(r, w, _TAG)",
        "        except Exception:",
        "            _channel = None",
        "    return _channel",
        "",
        "def _call_tool(tool_name: str, args: dict[str, Any]) -> Any:",
        '    dispatcher = globals().get("_mock_dispatcher")',
        "    if dispatcher is not None and callable(dispatcher):",
        "        return dispatcher(tool_name, args)",
        "",
        "    ch = _get_channel()",
        "    if ch is None:",
        '        raise RuntimeError("Code execution channel not available")',
        "",
        "    call_id = str(uuid.uuid4())",
        '    ch.send("tool_request", call_id, {"tool": tool_name, "args": args})',
        "    resp = ch.receive(timeout_s=120.0)",
        "    if resp is None:",
        '        raise RuntimeError(f"Tool \'{tool_name}\' call timed out or failed to receive response")',
        '    if resp.get("error"):',
        '        raise RuntimeError(str(resp["error"]))',
        '    return resp.get("result", resp.get("body", {}).get("result"))',
        "",
    ]

    for spec in specs:
        fn_name = spec.name.replace("-", "_").replace(".", "_")
        properties = spec.args_schema.get("properties", {})
        required = set(spec.args_schema.get("required", []))

        params: list[str] = []
        for prop_name, prop_data in properties.items():
            if not isinstance(prop_data, dict):
                prop_data = {}
            t_str = _map_type(prop_data)
            if prop_name in required:
                params.append(f"{prop_name}: {t_str}")
            else:
                params.append(f"{prop_name}: {t_str} | None = None")

        params.append("**kwargs: Any")
        param_signature = ", ".join(params)

        doc = spec.description.replace('"""', "'''") if spec.description else ""

        lines.append(f"def {fn_name}({param_signature}) -> Any:")
        lines.append(f'    """{doc}"""')
        arg_keys = [f'"{p}": {p}' for p in properties]
        if arg_keys:
            joined_keys = ", ".join(arg_keys)
            lines.append(f"    _args: dict[str, Any] = {{{joined_keys}}}")
            lines.append(
                "    _cleaned = {k: v for k, v in _args.items() if v is not None}"
            )
            lines.append("    _cleaned.update(kwargs)")
            lines.append(f'    return _call_tool("{spec.name}", _cleaned)')
        else:
            lines.append(f'    return _call_tool("{spec.name}", kwargs)')
        lines.append("")

    return "\n".join(lines)
