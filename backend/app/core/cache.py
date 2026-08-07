"""Cache service with an optional Redis/Valkey backend.

Ported from the fastapi-langgraph-agent template. Uses Valkey when
``VALKEY_HOST`` is configured, otherwise an in-process TTL cache. Only
successful values are ever stored.
"""

import hashlib
import time
from typing import (
    TYPE_CHECKING,
    Awaitable,
    Optional,
    cast,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from redis.asyncio import Redis  # pyright: ignore[reportMissingImports]

    REDIS_AVAILABLE = True
else:
    try:
        from redis.asyncio import Redis

        REDIS_AVAILABLE = True
    except ImportError:
        Redis = None
        REDIS_AVAILABLE = False


class InMemoryCacheService:
    """Simple in-memory TTL cache used when Valkey is not configured."""

    def __init__(self, default_ttl: int = 60):
        """Initialize the cache with a default TTL in seconds."""
        self._cache: dict[str, tuple[float, str]] = {}
        self._default_ttl = default_ttl

    async def initialize(self) -> None:
        """No-op for the in-memory backend."""
        logger.info("cache_initialized", backend="in_memory", ttl=self._default_ttl)

    async def get(self, key: str) -> Optional[str]:
        """Return a cached value, or ``None`` when missing or expired."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._cache[key]
            return None
        return value

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        """Store a value with a TTL."""
        self._cache[key] = (time.monotonic() + (ttl or self._default_ttl), value)

    async def delete(self, key: str) -> None:
        """Remove a value from the cache."""
        self._cache.pop(key, None)

    async def close(self) -> None:
        """Clear the cache."""
        self._cache.clear()


class ValkeyCacheService:
    """Redis/Valkey backend for distributed caching."""

    def __init__(self, default_ttl: int = 60):
        """Initialize the cache with a default TTL in seconds."""
        self._client: Optional["Redis"] = None
        self._default_ttl = default_ttl

    async def initialize(self) -> None:
        """Connect to the Valkey server."""
        client = Redis(
            host=settings.VALKEY_HOST,
            port=settings.VALKEY_PORT,
            db=settings.VALKEY_DB,
            password=settings.VALKEY_PASSWORD or None,
            max_connections=settings.VALKEY_MAX_CONNECTIONS,
            decode_responses=True,
        )
        await cast(Awaitable[bool], client.ping())
        self._client = client
        logger.info("cache_initialized", backend="valkey", host=settings.VALKEY_HOST, ttl=self._default_ttl)

    async def get(self, key: str) -> Optional[str]:
        """Return a cached value, or ``None`` on miss or transport failure."""
        if not self._client:
            return None
        try:
            return await self._client.get(key)
        except Exception as e:
            logger.warning("cache_get_failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        """Store a value with a TTL."""
        if not self._client:
            return
        try:
            await self._client.set(key, value, ex=(ttl or self._default_ttl))
        except Exception as e:
            logger.warning("cache_set_failed", key=key, error=str(e))

    async def delete(self, key: str) -> None:
        """Remove a value from the cache."""
        if not self._client:
            return
        try:
            await self._client.delete(key)
        except Exception as e:
            logger.warning("cache_delete_failed", key=key, error=str(e))

    async def close(self) -> None:
        """Close the Valkey connection."""
        if self._client:
            await self._client.aclose()
            logger.info("cache_connection_closed")


def _create_cache_service() -> InMemoryCacheService | ValkeyCacheService:
    """Pick the cache backend based on configuration."""
    ttl = settings.CACHE_TTL_SECONDS

    if settings.VALKEY_HOST and REDIS_AVAILABLE:
        return ValkeyCacheService(default_ttl=ttl)

    if settings.VALKEY_HOST and not REDIS_AVAILABLE:
        logger.warning("redis_client_not_installed", hint="uv add redis")

    return InMemoryCacheService(default_ttl=ttl)


def cache_key(prefix: str, *parts: str) -> str:
    """Build a deterministic cache key from a prefix and hashed parts."""
    hashed = hashlib.sha256(":".join(parts).encode()).hexdigest()[:16]
    return f"{prefix}:{hashed}"


cache_service = _create_cache_service()
