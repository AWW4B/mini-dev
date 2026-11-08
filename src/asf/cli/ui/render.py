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

from enum import StrEnum
from typing import Any


class OutputMode(StrEnum):
    RICH = "rich"
    PLAIN = "plain"
    JSON = "json"


class Renderer:
    def __init__(self, mode: OutputMode) -> None:
        raise NotImplementedError

    def table(self, title: str, columns: list[str], rows: list[list[Any]]) -> None:
        raise NotImplementedError

    def record(self, title: str, data: dict[str, Any]) -> None:
        raise NotImplementedError

    def tree(self, title: str, nodes: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    def message(self, text: str, level: str = "info") -> None:
        raise NotImplementedError
