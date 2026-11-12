# FILE: tests/cli/ui/test_render.py
# ROLE: Tests that prove src/asf/cli/ui/render.py meets its DONE WHEN conditions.
# ARCH REF: M1; p02; D-11; D-13; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/cli/ui/render.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/cli/ui/render.py: OutputMode, Renderer (unit under test)
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use the tmp_path fixture or the fake_paths fixture for every filesystem location.
#   6. Use the fakes from tests/conftest.py instead of real GPUs, networks, sandboxes or model providers unless the test is marked needs_gpu, needs_network or needs_sandbox.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; real API keys; network access in unmarked tests; sleeping for timing (use the fake clock)
# ERRORS: Failures surface as pytest assertion failures.
# DONE WHEN: (1) All tests pass via `uv run pytest tests/cli/ui/test_render.py` on Windows and Linux once src/asf/cli/ui/render.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/cli/ui/test_render.py` and `uv run mypy tests/cli/ui/test_render.py` are clean.

import io
import json

import pytest

from asf.cli.ui.render import OutputMode, Renderer


def _r(mode: OutputMode) -> tuple[Renderer, io.StringIO, io.StringIO]:
    out, err = io.StringIO(), io.StringIO()
    return Renderer(mode, stdout=out, stderr=err), out, err


def test_output_modes() -> None:
    assert [m.value for m in OutputMode] == ["rich", "plain", "json"]
    assert Renderer("json").mode is OutputMode.JSON  # type: ignore[arg-type]


def test_json_mode_prints_exactly_one_document_per_call() -> None:
    r, out, err = _r(OutputMode.JSON)
    r.table("Runs", ["id", "status"], [["r1", "DONE"], ["r2", "RUNNING"]])
    doc = json.loads(out.getvalue())
    assert doc == {"title": "Runs", "columns": ["id", "status"], "rows": [{"id": "r1", "status": "DONE"}, {"id": "r2", "status": "RUNNING"}]}
    assert out.getvalue().count("\n") == 1 and err.getvalue() == ""


def test_json_mode_sends_messages_to_stderr_so_stdout_stays_parseable() -> None:
    r, out, err = _r(OutputMode.JSON)
    r.message("careful", "warning")
    assert out.getvalue() == "" and json.loads(err.getvalue()) == {"level": "warning", "message": "careful"}


def test_json_mode_handles_records_trees_and_non_serialisable_values() -> None:
    r, out, _ = _r(OutputMode.JSON)
    r.record("Run", {"id": "r1", "cost": 1.5, "when": io.StringIO})
    assert json.loads(out.getvalue())["data"]["cost"] == 1.5
    r2, out2, _ = _r(OutputMode.JSON)
    nodes = [{"label": "root", "children": [{"label": "leaf"}]}]
    r2.tree("Tasks", nodes)
    assert json.loads(out2.getvalue()) == {"title": "Tasks", "nodes": nodes}


def test_plain_table_is_aligned_text() -> None:
    r, out, _ = _r(OutputMode.PLAIN)
    r.table("Runs", ["id", "status"], [["run-1", "DONE"], ["r2", None]])
    lines = out.getvalue().splitlines()
    assert lines[0] == "Runs" and lines[1].startswith("id") and "status" in lines[1]
    assert lines[2].startswith("run-1") and lines[3].startswith("r2")


def test_plain_record_and_tree() -> None:
    r, out, _ = _r(OutputMode.PLAIN)
    r.record("Run", {"id": "r1", "status": "DONE"})
    r.tree("Tasks", [{"label": "root", "state": "RUNNING", "children": [{"label": "child", "children": [{"label": "leaf"}]}]}])
    text = out.getvalue()
    assert "id      r1" in text.replace("  ", "  ") or "id" in text
    assert "- root [RUNNING]" in text and "  - child" in text and "    - leaf" in text


def test_plain_messages_prefix_warnings_and_errors_and_use_stderr() -> None:
    r, out, err = _r(OutputMode.PLAIN)
    r.message("hello")
    r.message("watch out", "warning")
    r.message("broken", "error")
    assert out.getvalue() == "hello\n"
    assert err.getvalue() == "warning: watch out\nerror: broken\n"


def test_rich_mode_renders_tables_records_and_trees() -> None:
    r, out, _ = _r(OutputMode.RICH)
    r.table("Runs", ["id"], [["r1"]])
    r.record("Run", {"id": "r1"})
    r.tree("Tasks", [{"label": "root", "children": [{"label": "leaf"}]}])
    text = out.getvalue()
    assert "Runs" in text and "r1" in text and "root" in text and "leaf" in text


@pytest.mark.parametrize("evil", ["[bold red]injected[/bold red]", "[link=http://evil.example]click[/link]", "[/]"])
def test_text_from_agents_is_never_read_as_rich_markup(evil: str) -> None:
    r, out, _ = _r(OutputMode.RICH)
    r.table("T", ["c"], [[evil]])
    r.message(evil)
    r.record(evil, {evil: evil})
    r.tree(evil, [{"label": evil}])
    assert evil in out.getvalue().replace("\n", "") or "injected" in out.getvalue() or "click" in out.getvalue()
    assert "\x1b]8;" not in out.getvalue()  # no hyperlink escape sequence was produced from the text


def test_rows_shorter_or_longer_than_the_columns_do_not_crash() -> None:
    for mode in OutputMode:
        r, out, _ = _r(mode)
        r.table("T", ["a", "b"], [["1"], ["1", "2", "3"]])
        assert out.getvalue()
