"""Rate limiting configuration.

Ported from the fastapi-langgraph-agent template. Limits are keyed on remote
address and backed by Valkey when configured, so they hold across instances.

Important: no ``SlowAPIMiddleware`` is installed, so ``RATE_LIMIT_DEFAULT`` only
applies to routes that carry an explicit ``@limiter.limit(...)`` decorator. The
existing business endpoints under ``/api`` are therefore never rate limited —
notably ``GET /api/companies``, which the settings page polls every 3 seconds.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.logging import logger

_storage_uri = None
if settings.VALKEY_HOST:
    _password_part = f":{settings.VALKEY_PASSWORD}@" if settings.VALKEY_PASSWORD else ""
    _storage_uri = f"redis://{_password_part}{settings.VALKEY_HOST}:{settings.VALKEY_PORT}/{settings.VALKEY_DB}"
    logger.info("rate_limiter_using_valkey", host=settings.VALKEY_HOST, port=settings.VALKEY_PORT)

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=settings.RATE_LIMIT_DEFAULT,  # pyright: ignore[reportArgumentType]
    storage_uri=_storage_uri,
)
