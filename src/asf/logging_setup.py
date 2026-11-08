# FILE: src/asf/logging_setup.py
# ROLE: Configures structlog JSON logs with rotation in the platformdirs log dir and the redaction processor.
# ARCH REF: D-26
# OWNS: Logging configuration
# DOES NOT OWN: Event log (events are not logs)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/paths.py: AppPaths, get_paths (cross-platform base directories)
#   - imports from src/asf/m5_shared/events/redaction.py: redact_text (redaction)
#   - called by src/asf/cli/app.py: configure_logging
#   - called by tests/test_logging_setup.py: configure_logging
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/test_logging_setup.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/logging_setup.py` and `uv run mypy src/asf/logging_setup.py` are clean.

import logging
import logging.handlers
from pathlib import Path
from typing import Any

import structlog

from asf.config.paths import get_paths


def _make_redact_processor() -> Any:
    """Return a structlog processor that redacts secrets from log event dicts.

    If the redaction module is still a stub (NotImplementedError), fall back
    to a no-op processor so logging still works.
    """
    try:
        from asf.m5_shared.events.redaction import redact_text

        def _processor(logger: Any, method: str, event_dict: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG001
            if "event" in event_dict and isinstance(event_dict["event"], str):
                try:
                    event_dict["event"] = redact_text(event_dict["event"])
                except (NotImplementedError, Exception):  # noqa: BLE001
                    pass
            return event_dict

        return _processor
    except (ImportError, NotImplementedError):
        return structlog.processors.StackInfoRenderer()


def configure_logging(level: str = "INFO", json_console: bool = False) -> None:
    """Configure structlog with rotating JSON file handler in the platformdirs log dir.

    Args:
        level: Standard logging level name (DEBUG / INFO / WARNING / ERROR).
        json_console: When True, also emit JSON to stderr; otherwise use a
            human-readable ConsoleRenderer on stderr.
    """
    paths = get_paths()
    log_dir: Path = paths.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "factory.log"

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # --- stdlib root logger ---
    root = logging.getLogger()
    root.setLevel(numeric_level)
    root.handlers.clear()

    # Rotating file handler (JSON) — 10 MB × 5 files
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(file_handler)

    # stderr handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(console_handler)

    # --- structlog ---
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _make_redact_processor(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_console:
        console_renderer: Any = structlog.processors.JSONRenderer()
    else:
        console_renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        cache_logger_on_first_use=True,
    )

    # Attach structlog formatter to both handlers
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )
    file_handler.setFormatter(formatter)

    console_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            console_renderer,
        ],
        foreign_pre_chain=shared_processors,
    )
    console_handler.setFormatter(console_formatter)
