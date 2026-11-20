# FILE: src/asf/m5_shared/trace.py
# ROLE: The flight recorder: one JSONL and one readable log per project with every traced event, where in the code it happened, and token and limit use.
# ARCH REF: M5; p12 Observability; D-14b
# OWNS: Trace sink (JSONL and text), trace_event, run context, stdlib log capture, optional function-call tracing
# DOES NOT OWN: Event log and narrative events (event_log.py); metrics tables (collector.py); console logging (logging_setup.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/events/redaction.py: redact_text (no secret reaches the trace)
#   - called by tests/m5_shared/test_trace.py: start_trace, stop_trace, trace_event, set_run, current_trace_paths, clip
#   - called by src/asf/m3_orchestration/run_graph.py: start_trace, set_run, trace_event
#   - called by src/asf/m5_shared/gateway/usage_callback.py: trace_event, clip
#   - called by src/asf/m5_shared/gateway/gateway.py: trace_event
#   - called by src/asf/m5_shared/state_store/store.py: trace_event
#   - called by src/asf/m5_shared/tools/executor.py: trace_event
#   - called by src/asf/m4_execution/scheduler.py: trace_event
#   - called by src/asf/m4_execution/worker/strategies.py: trace_event
#   - called by src/asf/m5_shared/memory/hooks.py: trace_event
#   - called by src/asf/m5_shared/decisions/broker.py: trace_event
#   - called by src/asf/m3_orchestration/decomposition/decomposition_graph.py: trace_event
#   - called by src/asf/m3_orchestration/planning/strategies.py: trace_event
#   - emits/consumes: writes <project>/.factory/logs/trace.jsonl and trace.log
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Tracing never raises into the caller and never blocks it for long: every public function swallows its own errors.
#   6. Every string is redacted and clipped before it is written; a prompt or a reply is stored as a preview with its full length.
#   7. Safe from any thread: one lock around the sinks.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/test_trace.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/trace.py` and `uv run mypy src/asf/m5_shared/trace.py` are clean.

import contextvars
import json
import logging
import os
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from asf.m5_shared.events.redaction import redact_text

PREVIEW_CHARS = 600
_PACKAGE_ROOT = Path(__file__).resolve().parents[1]  # src/asf
_run_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("asf_trace_run", default=None)
_lock = threading.Lock()
_state: dict[str, Any] = {"jsonl": None, "text": None, "paths": None, "t0": 0.0, "seq": 0, "handler": None, "run": None, "monitor": False}


def clip(value: Any, limit: int = PREVIEW_CHARS) -> Any:
    """A redacted, clipped copy of a value for the trace; a clipped string says how long the original was."""
    if isinstance(value, str):
        text = redact_text(value)
        return text if len(text) <= limit else f"{text[:limit]}...[{len(value)} chars]"
    if isinstance(value, dict):
        return {str(k): clip(v, limit) for k, v in list(value.items())[:60]}
    if isinstance(value, (list, tuple, set)):
        items = [clip(v, limit) for v in list(value)[:60]]
        return items if len(value) <= 60 else [*items, f"...[{len(value)} items]"]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return clip(repr(value), limit)


def set_run(run_id: str | None) -> None:
    """Tag every later event of this thread and its children with the run id (also the default for other threads)."""
    _run_var.set(run_id)
    _state["run"] = run_id


def current_trace_paths() -> tuple[Path, Path] | None:
    paths = _state["paths"]
    return paths if paths is not None else None


def _where(depth: int) -> str:
    try:
        frame = sys._getframe(depth)
        path = Path(frame.f_code.co_filename).resolve()
        try:
            shown = path.relative_to(_PACKAGE_ROOT.parent).as_posix()
        except ValueError:
            shown = path.name
        return f"{shown}:{frame.f_lineno} {frame.f_code.co_qualname}"
    except Exception:  # noqa: BLE001 - tracing must never raise
        return "?"


def _write(component: str, event: str, data: dict[str, Any], where: str) -> None:
    sink, text = _state["jsonl"], _state["text"]
    if sink is None:
        return
    now = time.time()
    with _lock:
        _state["seq"] += 1
        record = {
            "seq": _state["seq"], "ts": datetime.fromtimestamp(now, UTC).isoformat(timespec="milliseconds"), "t_s": round(now - _state["t0"], 3),
            "run_id": _run_var.get() or _state["run"], "thread": threading.current_thread().name, "component": component, "event": event,
            "where": where, "data": data,
        }
        sink.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        sink.flush()
        if text is not None:
            brief = " ".join(f"{k}={json.dumps(v, ensure_ascii=False, default=str)[:160]}" for k, v in data.items())
            text.write(f"{record['ts'][11:23]} #{record['seq']:<5} [{component}] {event} {brief}  @{where}\n")
            text.flush()


def trace_event(component: str, event: str, **data: Any) -> None:
    """Record one event with the file, line and function that called this."""
    if _state["jsonl"] is None:
        return
    try:
        _write(component, event, {k: clip(v) for k, v in data.items()}, _where(2))
    except Exception:  # noqa: BLE001 - tracing must never raise into the code it observes
        return


class _LogHandler(logging.Handler):
    """Every stdlib log record of the factory (warnings, errors with their traceback) goes into the trace with its own call site."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if not record.name.startswith("asf"):
                return
            data: dict[str, Any] = {"level": record.levelname, "logger": record.name, "message": clip(record.getMessage())}
            if record.exc_info and record.exc_info[1] is not None:
                data["exception"] = clip(f"{type(record.exc_info[1]).__name__}: {record.exc_info[1]}", 800)
            path = Path(record.pathname)
            try:
                shown = path.resolve().relative_to(_PACKAGE_ROOT.parent).as_posix()
            except ValueError:
                shown = path.name
            _write("log", record.levelname.lower(), data, f"{shown}:{record.lineno} {record.funcName}")
        except Exception:  # noqa: BLE001
            return


def _start_call_monitor() -> None:
    """Optional (FACTORY_TRACE=calls): every call of every function in the asf package, with its duration. Large; for hunting a hang."""
    mon = sys.monitoring
    tool = mon.PROFILER_ID
    try:
        mon.use_tool_id(tool, "asf-trace")
    except ValueError:
        return
    starts: dict[tuple[int, str], float] = {}
    root = str(_PACKAGE_ROOT)
    this_file = str(Path(__file__).resolve())

    def mine(code: Any) -> bool:
        name = code.co_filename
        return bool(name.startswith(root) and name != this_file)

    def on_start(code: Any, offset: int) -> Any:
        if not mine(code):
            return mon.DISABLE
        starts[(threading.get_ident(), code.co_qualname)] = time.perf_counter()
        _write("call", "enter", {}, f"{Path(code.co_filename).name}:{code.co_firstlineno} {code.co_qualname}")
        return None

    def on_return(code: Any, offset: int, retval: Any) -> Any:
        if not mine(code):
            return mon.DISABLE
        began = starts.pop((threading.get_ident(), code.co_qualname), None)
        _write("call", "exit", {"ms": round((time.perf_counter() - began) * 1000, 2) if began else None}, f"{Path(code.co_filename).name}:{code.co_firstlineno} {code.co_qualname}")
        return None

    mon.register_callback(tool, mon.events.PY_START, on_start)
    mon.register_callback(tool, mon.events.PY_RETURN, on_return)
    mon.set_events(tool, mon.events.PY_START | mon.events.PY_RETURN)
    _state["monitor"] = True


def start_trace(project_root: Path, run_id: str | None = None) -> Path:
    """Open (append to) <project>/.factory/logs/trace.jsonl and trace.log and start capturing log records. Returns the JSONL path."""
    mode = os.environ.get("FACTORY_TRACE", "on").lower()
    folder = Path(project_root) / ".factory" / "logs"
    jsonl_path, text_path = folder / "trace.jsonl", folder / "trace.log"
    try:
        if mode == "off":
            return jsonl_path
        folder.mkdir(parents=True, exist_ok=True)
        with _lock:
            if _state["jsonl"] is not None and _state["paths"] == (jsonl_path, text_path):
                set_run(run_id)
                return jsonl_path
            _close_locked()
            _state.update(jsonl=jsonl_path.open("a", encoding="utf-8"), text=text_path.open("a", encoding="utf-8"), paths=(jsonl_path, text_path), t0=time.time())
            handler = _LogHandler(logging.DEBUG)
            logging.getLogger().addHandler(handler)
            logging.getLogger().setLevel(min(logging.getLogger().level or logging.INFO, logging.DEBUG) if mode == "calls" else logging.getLogger().level)
            _state["handler"] = handler
        set_run(run_id)
        _write("trace", "started", {"project": str(project_root), "mode": mode, "pid": os.getpid()}, _where(2))
        if mode == "calls" and not _state["monitor"]:
            _start_call_monitor()
    except Exception:  # noqa: BLE001 - a project that cannot be traced still runs
        logging.getLogger(__name__).warning("could not start the trace in %s", folder, exc_info=True)
    return jsonl_path


def _close_locked() -> None:
    for key in ("jsonl", "text"):
        handle = _state[key]
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
        _state[key] = None
    handler = _state["handler"]
    if handler is not None:
        logging.getLogger().removeHandler(handler)
        _state["handler"] = None
    _state["paths"] = None


def stop_trace() -> None:
    with _lock:
        _close_locked()
        if _state["monitor"]:
            try:
                sys.monitoring.set_events(sys.monitoring.PROFILER_ID, 0)
                sys.monitoring.free_tool_id(sys.monitoring.PROFILER_ID)
            except Exception:  # noqa: BLE001, S110 - releasing the monitoring tool is best effort
                pass
            _state["monitor"] = False
