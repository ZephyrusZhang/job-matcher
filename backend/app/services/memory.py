"""Long-term memory service using mem0 and pgvector, with a cache layer.

Ported from the fastapi-langgraph-agent template.

Disabled by default via ``LONG_TERM_MEMORY_ENABLED``: mem0 needs an embeddings
endpoint, and the OpenAI-compatible providers this project targets (DeepSeek)
do not all expose one. Every method degrades to a no-op when disabled, so agents
can call them unconditionally.
"""

from typing import Optional

from mem0 import AsyncMemory

from app.core.cache import (
    cache_key,
    cache_service,
)
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class MemoryService:
    """Semantic long-term memory, partitioned per user."""

    def __init__(self):
        """Prepare the service without connecting to the vector store."""
        self._memory: Optional[AsyncMemory] = None

    @property
    def enabled(self) -> bool:
        """Whether long-term memory is turned on."""
        return settings.LONG_TERM_MEMORY_ENABLED

    async def _get_memory(self) -> AsyncMemory:
        """Return the mem0 instance, building it on first use."""
        if self._memory is None:
            llm_config: dict = {"model": settings.LONG_TERM_MEMORY_MODEL}
            embedder_config: dict = {"model": settings.LONG_TERM_MEMORY_EMBEDDER_MODEL}
            if settings.LLM_BASE_URL:
                llm_config["openai_base_url"] = settings.LLM_BASE_URL
            if settings.LLM_API_KEY:
                llm_config["api_key"] = settings.LLM_API_KEY

            self._memory = await AsyncMemory.from_config(
                config_dict={
                    "vector_store": {
                        "provider": "pgvector",
                        "config": {
                            "collection_name": settings.LONG_TERM_MEMORY_COLLECTION_NAME,
                            "dbname": settings.POSTGRES_DB,
                            "user": settings.POSTGRES_USER,
                            "password": settings.POSTGRES_PASSWORD,
                            "host": settings.POSTGRES_HOST,
                            "port": settings.POSTGRES_PORT,
                        },
                    },
                    "llm": {"provider": "openai", "config": llm_config},
                    "embedder": {"provider": "openai", "config": embedder_config},
                }
            )
        return self._memory

    async def initialize(self) -> None:
        """Pre-warm mem0 so the first search or add does not pay cold-init cost."""
        if not self.enabled:
            logger.info("memory_service_disabled")
            return
        await self._get_memory()
        logger.info("memory_service_initialized")

    async def search(self, user_id: str | None, query: str) -> str:
        """Return memories relevant to a query, checking the cache first.

        Args:
            user_id: Memory partition. ``None`` skips long-term memory rather
                than pooling anonymous sessions into a shared partition.
            query: The text to search for.

        Returns:
            A newline-separated memory list, or an empty string on miss/failure.
        """
        if not self.enabled or user_id is None:
            return ""
        try:
            key = cache_key("memory", str(user_id), query)
            cached = await cache_service.get(key)
            if cached is not None:
                logger.debug("memory_search_cache_hit", user_id=user_id)
                return cached

            memory = await self._get_memory()
            results = await memory.search(user_id=str(user_id), query=query)
            result = "\n".join(f"* {r['memory']}" for r in results["results"])

            if result:
                await cache_service.set(key, result)
            return result
        except Exception as e:
            logger.warning("failed_to_get_relevant_memory", error=str(e), user_id=user_id)
            return ""

    async def add(self, user_id: str | None, messages: list[dict], metadata: dict | None = None) -> None:
        """Persist conversation messages into long-term memory.

        Args:
            user_id: Memory partition. ``None`` is a no-op.
            messages: OpenAI-style message dicts.
            metadata: Optional metadata stored alongside the memories.
        """
        if not self.enabled or user_id is None:
            return
        try:
            memory = await self._get_memory()
            await memory.add(messages, user_id=str(user_id), metadata=metadata)
            logger.info("long_term_memory_updated_successfully", user_id=user_id)
        except Exception as e:
            logger.warning("failed_to_update_long_term_memory", user_id=user_id, error=str(e))


memory_service = MemoryService()
