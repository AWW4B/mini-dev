# FILE: src/asf/cli/views/dash_view.py
# ROLE: Live dashboard: VRAM/RAM, slots, tokens, cost (EST flags), queue, controls hint.
# ARCH REF: M1; p02 Resource Dashboard; IF-19; IF-20
# OWNS: Rendering this view
# DOES NOT OWN: Data production
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/metrics.py: MetricsSnapshot (IF-19)
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (rich / plain / JSON output)
#   - called by src/asf/cli/commands/dash.py: DashView
#   - called by tests/cli/views/test_dash_view.py: DashView
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Escape all agent/tool text before rendering; never execute or interpret it.
#   6. Refresh using cursors, not busy loops.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/cli/views/test_dash_view.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/views/dash_view.py` and `uv run mypy src/asf/cli/views/dash_view.py` are clean.

from typing import Any


class DashView:
    def __init__(self, renderer: Any, run_id: str | None) -> None:
        raise NotImplementedError

    def render_once(self) -> None:
        raise NotImplementedError

    def live(self) -> None:
        """Refresh until Ctrl+C (which only exits the view)."""
        raise NotImplementedError
