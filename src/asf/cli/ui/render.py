# FILE: src/asf/cli/ui/render.py
# ROLE: Renders tables, trees, panels and records in rich, plain or JSON mode.
# ARCH REF: M1; p02; D-11; D-13
# OWNS: Output formatting
# DOES NOT OWN: Data retrieval
# CONNECTS TO (external boundaries only):
#   - called by src/asf/cli/commands/doctor.py: OutputMode, Renderer
#   - called by src/asf/cli/commands/init.py: OutputMode, Renderer
#   - called by src/asf/cli/commands/project.py: OutputMode, Renderer
#   - called by src/asf/cli/commands/run.py: OutputMode, Renderer
#   - called by src/asf/cli/commands/trace.py: OutputMode, Renderer
#   - called by src/asf/cli/commands/inbox.py: OutputMode, Renderer
#   - called by src/asf/cli/commands/dash.py: OutputMode, Renderer
#   - called by src/asf/cli/commands/tasks.py: OutputMode, Renderer
#   - called by src/asf/cli/commands/history.py: OutputMode, Renderer
#   - called by src/asf/cli/commands/report.py: OutputMode, Renderer
#   - called by src/asf/cli/commands/models.py: OutputMode, Renderer
#   - called by src/asf/cli/commands/skills.py: OutputMode, Renderer
#   - called by src/asf/cli/commands/events.py: OutputMode, Renderer
#   - called by src/asf/cli/commands/config_cmd.py: OutputMode, Renderer
#   - called by src/asf/cli/commands/stats.py: OutputMode, Renderer
#   - called by src/asf/cli/commands/mcp.py: OutputMode, Renderer
#   - called by src/asf/cli/commands/web.py: OutputMode, Renderer
#   - called by src/asf/cli/views/trace_view.py: OutputMode, Renderer
#   - called by src/asf/cli/views/inbox_view.py: OutputMode, Renderer
#   - called by src/asf/cli/views/dash_view.py: OutputMode, Renderer
#   - called by src/asf/cli/views/task_tree_view.py: OutputMode, Renderer
#   - called by tests/cli/ui/test_render.py: OutputMode, Renderer
#   - called by src/asf/cli/context.py: OutputMode, Renderer
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. JSON mode prints exactly one JSON document to stdout; logs go to stderr.
#   6. Escape Rich markup in any text that came from agents, documents or tools.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/cli/ui/test_render.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/ui/render.py` and `uv run mypy src/asf/cli/ui/render.py` are clean.

import json
import sys
from enum import StrEnum
from typing import Any, TextIO

from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.tree import Tree


class OutputMode(StrEnum):
    RICH = "rich"
    PLAIN = "plain"
    JSON = "json"


_STYLES = {"info": "", "success": "green", "warning": "yellow", "error": "bold red"}


def _cell(value: Any) -> str:
    return "" if value is None else str(value)


class Renderer:
    """One output interface for rich, plain and JSON.

    JSON mode prints exactly one JSON document per call to stdout and sends messages to stderr, so ``--output json`` stays
    machine-readable. Text that came from agents, documents or tools is escaped before Rich can read it as markup.
    """

    def __init__(self, mode: OutputMode, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> None:
        self.mode = OutputMode(mode)
        self._stdout = stdout
        self._stderr = stderr

    @property
    def out(self) -> TextIO:
        return self._stdout if self._stdout is not None else sys.stdout

    @property
    def err(self) -> TextIO:
        return self._stderr if self._stderr is not None else sys.stderr

    def _console(self, stream: TextIO) -> Console:
        return Console(file=stream, highlight=False, soft_wrap=True)

    def _json(self, document: dict[str, Any]) -> None:
        self.out.write(json.dumps(document, default=str, ensure_ascii=False) + "\n")

    def table(self, title: str, columns: list[str], rows: list[list[Any]]) -> None:
        if self.mode is OutputMode.JSON:
            self._json({"title": title, "columns": columns, "rows": [dict(zip(columns, row, strict=False)) for row in rows]})
        elif self.mode is OutputMode.PLAIN:
            cells = [[_cell(c) for c in row] for row in rows]
            widths = [max([len(columns[i]), *(len(r[i]) for r in cells if i < len(r))]) for i in range(len(columns))]
            lines = [title, "  ".join(c.ljust(w) for c, w in zip(columns, widths, strict=True)).rstrip()]
            lines += ["  ".join(c.ljust(w) for c, w in zip(r, widths, strict=False)).rstrip() for r in cells]
            self.out.write("\n".join(lines) + "\n")
        else:
            table = Table(title=escape(title))
            for column in columns:
                table.add_column(escape(column))
            for row in rows:
                table.add_row(*(escape(_cell(c)) for c in row))
            self._console(self.out).print(table)

    def record(self, title: str, data: dict[str, Any]) -> None:
        if self.mode is OutputMode.JSON:
            self._json({"title": title, "data": data})
        elif self.mode is OutputMode.PLAIN:
            width = max((len(str(k)) for k in data), default=0)
            self.out.write("\n".join([title, *(f"{str(k).ljust(width)}  {_cell(v)}" for k, v in data.items())]) + "\n")
        else:
            table = Table(title=escape(title), show_header=False)
            table.add_column(style="bold")
            table.add_column()
            for key, value in data.items():
                table.add_row(escape(str(key)), escape(_cell(value)))
            self._console(self.out).print(table)

    def tree(self, title: str, nodes: list[dict[str, Any]]) -> None:
        """``nodes`` is a list of {"label": str, "state": optional str, "children": [same shape]}."""
        if self.mode is OutputMode.JSON:
            self._json({"title": title, "nodes": nodes})
            return

        def label(node: dict[str, Any]) -> str:
            state = f" [{node['state']}]" if node.get("state") else ""
            return f"{node.get('label', '')}{state}"

        if self.mode is OutputMode.PLAIN:
            lines = [title]

            def walk(items: list[dict[str, Any]], depth: int) -> None:
                for item in items:
                    lines.append("  " * depth + "- " + label(item))
                    walk(item.get("children", []), depth + 1)

            walk(nodes, 0)
            self.out.write("\n".join(lines) + "\n")
        else:
            root = Tree(escape(title))

            def build(parent: Tree, items: list[dict[str, Any]]) -> None:
                for item in items:
                    build(parent.add(escape(label(item))), item.get("children", []))

            build(root, nodes)
            self._console(self.out).print(root)

    def message(self, text: str, level: str = "info") -> None:
        if self.mode is OutputMode.JSON:
            self.err.write(json.dumps({"level": level, "message": text}, ensure_ascii=False) + "\n")
            return
        stream = self.err if level in ("warning", "error") else self.out
        if self.mode is OutputMode.PLAIN:
            prefix = "" if level in ("info", "success") else f"{level}: "
            stream.write(prefix + text + "\n")
        else:
            style = _STYLES.get(level, "")
            self._console(stream).print(escape(text), style=style or None)
