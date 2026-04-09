"""Read-only mode middleware.

When the environment variable ``READ_ONLY_MODE`` is truthy (``true``/``1``/``yes``),
this middleware blocks any request that would mutate state or invoke the
three features the cloud demo does not expose:

* ``/api/match/*``      — smart recommendation (entire feature)
* ``/api/compare/*``    — job comparison (entire feature)
* ``/api/settings``     — write methods only (display preferences)
* ``/api/companies``    — write methods only (CRUD from settings page)
* ``/api/crawl``        — write methods only (trigger/cancel from settings page)
* ``/api/resume``       — write methods only (resume upload used by match/compare)

Read methods on settings/companies/crawl/resume remain allowed so the jobs
browsing pages keep working (e.g. the job list needs ``GET /api/companies``).

The middleware is deliberately independent from ``AppConfig`` so the same
binary can be deployed as either a full instance or a demo instance purely
via environment variables.
"""

from __future__ import annotations

import logging
import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

_TRUTHY = {"1", "true", "yes", "on"}

# Feature prefixes that are blocked regardless of HTTP method.
_BLOCKED_FEATURE_PREFIXES: tuple[str, ...] = (
    "/api/match",
    "/api/compare",
)

# Prefixes whose *write* methods are blocked (GET/HEAD/OPTIONS stay allowed).
_WRITE_BLOCKED_PREFIXES: tuple[str, ...] = (
    "/api/settings",
    "/api/companies",
    "/api/crawl",
    "/api/resume",
)

_WRITE_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def is_read_only_mode() -> bool:
    """Return True if the process is running in read-only demo mode."""
    return os.getenv("READ_ONLY_MODE", "").strip().lower() in _TRUTHY


def _is_blocked(method: str, path: str) -> bool:
    for prefix in _BLOCKED_FEATURE_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return True
    if method.upper() in _WRITE_METHODS:
        for prefix in _WRITE_BLOCKED_PREFIXES:
            if path == prefix or path.startswith(prefix + "/"):
                return True
    return False


class ReadOnlyMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that rejects editing requests when read-only mode is on."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._enabled = is_read_only_mode()
        if self._enabled:
            logger.warning(
                "READ_ONLY_MODE is ENABLED — match/compare/settings/companies/crawl/"
                "resume write endpoints will return HTTP 403."
            )

    async def dispatch(self, request: Request, call_next):
        if self._enabled and _is_blocked(request.method, request.url.path):
            logger.info(
                "ReadOnlyMiddleware blocked %s %s", request.method, request.url.path
            )
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "READ_ONLY_MODE",
                        "message": (
                            "该功能在演示环境中不可用，如需使用请自行部署完整版。"
                        ),
                    },
                    "pagination": None,
                },
            )
        return await call_next(request)
