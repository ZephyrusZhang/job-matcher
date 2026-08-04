"""Cross-cutting ASGI middleware for metrics and logging context.

Ported from the fastapi-langgraph-agent template.
"""

import time
from typing import Callable

from fastapi import Request
from jose import (
    JWTError,
    jwt,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.core.logging import (
    bind_context,
    clear_context,
)
from app.core.metrics import (
    http_request_duration_seconds,
    http_requests_total,
)


def _endpoint_label(request: Request) -> str:
    """Return a low-cardinality endpoint label for Prometheus.

    Uses the matched route template (``/api/jobs/{job_id}``) rather than the raw
    path, so per-job URLs do not each create their own metric series.
    """
    route = request.scope.get("route")
    path_format = getattr(route, "path", None)
    return path_format or request.url.path


class MetricsMiddleware(BaseHTTPMiddleware):
    """Track request count and duration for every HTTP request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Record metrics around the downstream handler."""
        start_time = time.time()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = time.time() - start_time
            endpoint = _endpoint_label(request)
            http_requests_total.labels(method=request.method, endpoint=endpoint, status=status_code).inc()
            http_request_duration_seconds.labels(method=request.method, endpoint=endpoint).observe(duration)


class LoggingContextMiddleware(BaseHTTPMiddleware):
    """Bind session_id / user_id from a bearer token into the logging context.

    Requests without a token — which is every existing business endpoint — pass
    straight through untouched.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Populate the request-scoped logging context, then always clear it."""
        try:
            clear_context()

            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer ") and settings.JWT_SECRET_KEY:
                token = auth_header.split(" ", 1)[1]
                try:
                    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
                    session_id = payload.get("sub")
                    if session_id:
                        bind_context(session_id=session_id)
                except JWTError:
                    # Invalid token — let the auth dependency produce the 401.
                    pass

            response = await call_next(request)

            if hasattr(request.state, "user_id"):
                bind_context(user_id=request.state.user_id)

            return response
        finally:
            clear_context()
