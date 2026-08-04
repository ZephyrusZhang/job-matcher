"""Structured logging for the agent framework.

Ported from the fastapi-langgraph-agent template. Configures structlog with a
console renderer in development and JSON in production, writes a daily JSONL
file, and injects request-scoped context (request_id, session_id, user_id) into
every event.

Existing modules that use ``logging.getLogger(__name__)`` keep working — their
records flow through the same handlers configured here.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from asgi_correlation_id import correlation_id

from app.core.config import (
    Environment,
    settings,
)

settings.LOG_DIR.mkdir(parents=True, exist_ok=True)

_request_context: ContextVar[dict[str, Any] | None] = ContextVar("request_context", default=None)


def bind_context(**kwargs: Any) -> None:
    """Bind context variables to the current request."""
    current = _request_context.get() or {}
    _request_context.set({**current, **kwargs})


def clear_context() -> None:
    """Clear all context variables for the current request."""
    _request_context.set(None)


def get_context() -> dict[str, Any]:
    """Return the current logging context."""
    return _request_context.get() or {}


def add_context_to_event_dict(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Merge bound context variables into each log event."""
    context = get_context()
    if context:
        event_dict.update(context)
    return event_dict


def add_request_id_to_event_dict(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Add the current correlation id to each log event."""
    request_id = correlation_id.get()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict


def get_log_file_path() -> Path:
    """Return the dated JSONL log file path for the current environment."""
    return settings.LOG_DIR / f"{settings.ENVIRONMENT.value}-{datetime.now().strftime('%Y-%m-%d')}.jsonl"


class JsonlFileHandler(logging.Handler):
    """Handler writing one JSON object per line to a daily file."""

    def __init__(self, file_path: Path):
        """Initialize the handler with a target file path."""
        super().__init__()
        self.file_path = file_path

    def emit(self, record: logging.LogRecord) -> None:
        """Write a single record as a JSON line."""
        try:
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
                "environment": settings.ENVIRONMENT.value,
            }
            extra = getattr(record, "extra", None)
            if isinstance(extra, dict):
                log_entry.update(extra)

            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False, default=str) + "\n")
        except Exception:
            self.handleError(record)


def get_structlog_processors(include_file_info: bool = True) -> list[Any]:
    """Build the structlog processor chain."""
    processors: list[Any] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        add_context_to_event_dict,
        add_request_id_to_event_dict,
    ]

    if include_file_info:
        processors.append(
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                }
            )
        )

    processors.append(lambda _, __, event_dict: {**event_dict, "environment": settings.ENVIRONMENT.value})
    return processors


def setup_logging() -> None:
    """Configure structlog and the stdlib root logger."""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    file_handler = JsonlFileHandler(get_log_file_path())
    file_handler.setLevel(log_level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    shared_processors = get_structlog_processors(
        include_file_info=settings.ENVIRONMENT in (Environment.DEVELOPMENT, Environment.TEST)
    )

    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=[file_handler, console_handler],
        force=True,
    )

    renderer = (
        structlog.dev.ConsoleRenderer() if settings.LOG_FORMAT == "console" else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


setup_logging()

logger = structlog.get_logger()
