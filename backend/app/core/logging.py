"""Structured logging.

One logging setup for the whole backend — the agent framework and the business
code both go through it. Modules get their own logger::

    from app.core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("crawl_started", company=company_id, mode=mode)

Events are named in ``snake_case`` and everything variable goes in keyword
arguments, never interpolated into the name. That is what makes a log
greppable: ``grep crawl_failed`` finds every occurrence regardless of which
company or task it was about.

Two sinks, deliberately different:

* **console** — for a human watching the server. Rendered, coloured, one line
  per event, with the constant fields (environment, callsite) left out unless
  the level is DEBUG.
* **daily JSONL file** — for after the fact. Every field kept as a real JSON
  key so it can be queried: ``jq 'select(.event=="crawl_failed")'``.

Both are fed from the same event dict via ``ProcessorFormatter``, so they can
never disagree about what happened.
"""

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

# Third-party loggers that carry no signal for this application and a great
# deal of volume. Left unconfigured, a single day of development wrote 1.3 GB:
# `aiosqlite` DEBUG-logs every statement it runs *and* the callable's repr, so
# `_CREATE_TABLES_SQL` — 10 KB of DDL — was re-logged on every new connection.
#
# `psycopg_pool` is capped at ERROR rather than WARNING because it warns on
# every reconnect attempt while the agent Postgres is down, which is a retry
# storm rather than N distinct problems. The one-line summary that actually
# matters is emitted by the lifespan itself as `agent_checkpointer_unavailable`.
_THIRD_PARTY_LEVELS: dict[str, int] = {
    "aiosqlite": logging.WARNING,
    "asyncio": logging.WARNING,
    "docker": logging.WARNING,
    "urllib3": logging.WARNING,
    "httpcore": logging.WARNING,
    "httpx": logging.WARNING,
    "openai": logging.WARNING,
    "langfuse": logging.WARNING,
    "psycopg": logging.WARNING,
    # The logger is "psycopg.pool" — note the dot. It warns once per reconnect
    # attempt while the agent Postgres is down, which is one problem reported
    # dozens of times, not dozens of problems.
    "psycopg.pool": logging.ERROR,
    "watchfiles": logging.WARNING,
    "python_multipart": logging.WARNING,
    "multipart": logging.WARNING,
}

class ThirdPartyLevelFilter(logging.Filter):
    """Enforce ``_THIRD_PARTY_LEVELS`` at the handler.

    Setting the level on the library's own logger is not enough: several of
    these configure themselves when *they* are imported, which happens after
    this module runs, and they raise their own level back up. Langfuse in
    particular restores INFO and then announces its public key on every boot.
    A filter on the handler runs last and cannot be overridden.
    """

    #: Longest prefix first, so "psycopg.pool" wins over "psycopg" instead of
    #: whichever happens to come first in the dict.
    _ORDERED = sorted(_THIRD_PARTY_LEVELS.items(), key=lambda kv: len(kv[0]), reverse=True)

    def filter(self, record: logging.LogRecord) -> bool:
        for prefix, level in self._ORDERED:
            if record.name == prefix or record.name.startswith(prefix + "."):
                return record.levelno >= level
        return True


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


def get_logger(name: str | None = None) -> Any:
    """Return a logger bound to ``name`` — pass ``__name__``.

    Modules must not share one logger instance. ``structlog.get_logger()`` with
    no name resolves it from the calling frame, and with
    ``cache_logger_on_first_use`` that name is frozen on first use — so a single
    shared instance reports whichever module happened to log first for *every*
    event. That is how ``agent_initialized``, ``cache_initialized`` and
    ``llm_service_initialized`` all came to be attributed to
    ``app.core.observability``, leaving no way to tell where an event came from.
    """
    return structlog.get_logger(name)


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


def add_environment(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Tag the event with the environment it came from."""
    event_dict["environment"] = settings.ENVIRONMENT.value
    return event_dict


def shorten_logger_name(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Drop the ``app.`` prefix so the console column stays narrow.

    ``app.services.crawl_service`` reads as ``services.crawl_service``; the full
    name is still written to the JSONL file.
    """
    name = event_dict.get("logger")
    if isinstance(name, str) and name.startswith("app."):
        event_dict["logger"] = name[4:]
    return event_dict


def get_log_file_path() -> Path:
    """Return the dated JSONL log file path for the current environment."""
    return settings.LOG_DIR / f"{settings.ENVIRONMENT.value}-{datetime.now().strftime('%Y-%m-%d')}.jsonl"


def _resolve_level() -> int:
    """Resolve the log level from ``LOG_LEVEL``, falling back to ``DEBUG``.

    ``LOG_LEVEL`` is set per environment in ``core/config.py`` but used to be
    ignored here in favour of ``DEBUG``, which is why development ran at DEBUG
    and pulled in every third-party debug line.
    """
    configured = getattr(settings, "LOG_LEVEL", None)
    if isinstance(configured, str):
        level = logging.getLevelNamesMapping().get(configured.upper())
        if level is not None:
            return level
    return logging.DEBUG if settings.DEBUG else logging.INFO


#: Fields every event carries that a human reading the console does not need —
#: the environment never varies within a process, and the callsite is only
#: interesting once you are already chasing something. They stay in the JSONL.
_CONSOLE_HIDDEN = ("environment", "filename", "func_name", "lineno")


def _shared_processors() -> list[Any]:
    """Processors applied to every event before it reaches a renderer."""
    return [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        add_context_to_event_dict,
        add_request_id_to_event_dict,
        add_environment,
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
    ]


def _console_processors(verbose: bool) -> list[Any]:
    """Trim an event down to what a human watching the terminal wants."""

    def prune(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        if not verbose:
            for key in _CONSOLE_HIDDEN:
                event_dict.pop(key, None)
        return event_dict

    return [
        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
        shorten_logger_name,
        prune,
        structlog.dev.ConsoleRenderer(pad_event=28, colors=sys.stdout.isatty()),
    ]


def setup_logging() -> None:
    """Configure structlog and the stdlib root logger."""
    level = _resolve_level()
    verbose = level <= logging.DEBUG
    shared = _shared_processors()

    # Foreign records (uvicorn, langchain, anything using stdlib logging) are
    # run through the same chain so they come out looking like everything else.
    foreign_chain = [structlog.stdlib.ExtraAdder(), *shared]

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=_console_processors(verbose)
            if settings.LOG_FORMAT == "console"
            else [structlog.processors.JSONRenderer()],
            foreign_pre_chain=foreign_chain,
        )
    )

    # The file is always JSON, whatever the console is doing. It used to receive
    # the *rendered* console string as its "message" field — ANSI escapes and
    # all — which made the JSONL unqueryable despite the extension.
    file_handler = logging.FileHandler(get_log_file_path(), encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.dict_tracebacks,
                structlog.processors.JSONRenderer(ensure_ascii=False),
            ],
            foreign_pre_chain=foreign_chain,
        )
    )

    noise_filter = ThirdPartyLevelFilter()
    console_handler.addFilter(noise_filter)
    file_handler.addFilter(noise_filter)

    logging.basicConfig(level=level, handlers=[console_handler, file_handler], force=True)

    # Belt and braces: setting the level too means the records are never even
    # formatted, which is what saves the work on aiosqlite's per-statement repr.
    for name, third_party_level in _THIRD_PARTY_LEVELS.items():
        logging.getLogger(name).setLevel(third_party_level)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared,
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


setup_logging()

#: Fallback logger. Prefer ``get_logger(__name__)`` in new code so the event can
#: be traced back to a module.
logger = structlog.get_logger("app")
