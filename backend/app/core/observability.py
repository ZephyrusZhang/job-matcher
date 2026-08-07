"""Langfuse tracing for all LLM and agent operations.

Ported from the fastapi-langgraph-agent template.

``langfuse_init()`` must run before the callback handler is constructed: the
handler resolves the process-wide Langfuse client via ``get_client()``, and
whichever call creates that singleton first — this one, carrying an explicit
``environment=`` — wins. A later ``langfuse_init()`` cannot retroactively fix
the environment tag on an already-created singleton.
"""

from typing import Optional

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def langfuse_init() -> None:
    """Initialize the process-wide Langfuse client."""
    if not settings.LANGFUSE_TRACING_ENABLED:
        logger.debug("langfuse_tracing_disabled")
        return

    langfuse = Langfuse(
        tracing_enabled=settings.LANGFUSE_TRACING_ENABLED,
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
        environment=settings.ENVIRONMENT.value,
        debug=settings.DEBUG,
    )

    try:
        if langfuse.auth_check():
            logger.debug("langfuse_auth_success")
        else:
            logger.warning("langfuse_auth_failure")
    except Exception:
        logger.exception("langfuse_auth_check_failed")


def get_langfuse_callback_handler() -> Optional[CallbackHandler]:
    """Build a Langfuse callback handler, or ``None`` when tracing is disabled."""
    if not settings.LANGFUSE_TRACING_ENABLED:
        return None
    try:
        return CallbackHandler()
    except Exception:
        logger.exception("langfuse_callback_handler_creation_failed")
        return None


def flush_langfuse() -> None:
    """Force-send any queued spans.

    Langfuse batches spans and exports them in the background, so a process that
    exits shortly after an agent run can drop the tail of a trace. Call this on
    shutdown — and after any short-lived script — so nothing is lost.
    """
    if not settings.LANGFUSE_TRACING_ENABLED:
        return
    try:
        from langfuse import get_client

        get_client().flush()
        logger.info("langfuse_flushed")
    except Exception:
        logger.warning("langfuse_flush_failed")


langfuse_init()
langfuse_callback_handler = get_langfuse_callback_handler()
