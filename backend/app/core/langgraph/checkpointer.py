"""Shared Postgres checkpointer for stateful agent conversations.

Ported from the fastapi-langgraph-agent template, with the connection pool
lifted out of the agent class so every agent shares one pool instead of opening
its own.

The pool is bound to the event loop that first opens it, so all agents must run
on the application's main loop. That is why agent tools wrap blocking work in
``asyncio.to_thread`` rather than running whole agents in worker threads.
"""

from typing import Optional

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg import sql
from psycopg.rows import (
    DictRow,
    dict_row,
)
from psycopg_pool import AsyncConnectionPool

from app.core.config import (
    Environment,
    settings,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

PostgresConnPool = AsyncConnectionPool[AsyncConnection[DictRow]]

_connection_pool: Optional[PostgresConnPool] = None
_checkpointer: Optional[AsyncPostgresSaver] = None


async def get_connection_pool() -> Optional[PostgresConnPool]:
    """Return the shared Postgres pool, opening it on first use.

    Returns:
        The pool, or ``None`` when it cannot be opened in production (the app
        keeps running in a degraded, checkpoint-less mode).

    Raises:
        Exception: Propagated outside production so misconfiguration is loud.
    """
    global _connection_pool

    if _connection_pool is None:
        try:
            _connection_pool = AsyncConnectionPool(
                settings.postgres_url(),
                open=False,
                max_size=settings.POSTGRES_POOL_SIZE,
                kwargs={
                    "autocommit": True,
                    "connect_timeout": 5,
                    "prepare_threshold": None,
                    "row_factory": dict_row,
                },
            )
            await _connection_pool.open()
            logger.info(
                "agent_connection_pool_created",
                max_size=settings.POSTGRES_POOL_SIZE,
                host=settings.POSTGRES_HOST,
                database=settings.POSTGRES_DB,
            )
        except Exception as e:
            _connection_pool = None
            logger.error("agent_connection_pool_creation_failed", error=str(e))
            if settings.ENVIRONMENT == Environment.PRODUCTION:
                logger.warning("continuing_without_connection_pool")
                return None
            raise

    return _connection_pool


async def get_checkpointer() -> Optional[AsyncPostgresSaver]:
    """Return the shared checkpointer, running table setup once.

    Returns:
        The checkpointer, or ``None`` when no pool is available.
    """
    global _checkpointer

    if _checkpointer is None:
        pool = await get_connection_pool()
        if pool is None:
            return None
        _checkpointer = AsyncPostgresSaver(pool)
        await _checkpointer.setup()
        logger.info("agent_checkpointer_ready")

    return _checkpointer


async def clear_thread(thread_id: str) -> None:
    """Delete every checkpoint row belonging to a thread.

    Args:
        thread_id: The LangGraph thread (agent session) to clear.

    Raises:
        RuntimeError: When the connection pool is unavailable.
    """
    pool = await get_connection_pool()
    if pool is None:
        raise RuntimeError("connection pool unavailable; cannot clear thread")

    async with pool.connection() as conn:
        async with conn.pipeline():
            for table in settings.CHECKPOINT_TABLES:
                await conn.execute(
                    sql.SQL("DELETE FROM {} WHERE thread_id = %s").format(sql.Identifier(table)),
                    (thread_id,),
                )
    logger.info("checkpoint_tables_cleared_for_thread", tables=settings.CHECKPOINT_TABLES, thread_id=thread_id)


async def close_connection_pool() -> None:
    """Close the shared pool on application shutdown."""
    global _connection_pool, _checkpointer

    if _connection_pool is not None:
        await _connection_pool.close()
        logger.info("agent_connection_pool_closed")

    _connection_pool = None
    _checkpointer = None
