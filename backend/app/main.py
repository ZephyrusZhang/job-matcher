import logging
from contextlib import asynccontextmanager
from pathlib import Path

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import load_config
# Importing app.core.logging configures structlog and the root logger, so it
# must come before any module that logs at import time.
from app.core.logging import logger as struct_logger
from app.core.cache import cache_service
from app.core.config import settings as agent_settings
from app.core.langgraph import close_connection_pool, get_checkpointer
from app.core.limiter import limiter
from app.core.metrics import setup_metrics
from app.core.middleware import LoggingContextMiddleware, MetricsMiddleware
from app.core.observability import flush_langfuse
from app.database import init_database
from app.dependencies import init_services
from app.exceptions import AppError
from app.middleware import ReadOnlyMiddleware
from app.routers import (
    chat,
    companies,
    compare,
    crawl,
    favorites,
    jobs,
    match,
    resume,
    settings,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Resolve config dir relative to backend/
    backend_dir = Path(__file__).resolve().parent.parent
    config = load_config(str(backend_dir / "config"))

    # Resolve relative paths to be relative to backend/
    if not Path(config.database.path).is_absolute():
        config.database.path = str(backend_dir / config.database.path)
    if not Path(config.uploads.dir).is_absolute():
        config.uploads.dir = str(backend_dir / config.uploads.dir)

    await init_database(config.database)
    await init_services(config, config.database.path)

    # ── Agent framework ──
    # Every step degrades gracefully: the business API must keep serving even
    # when the agent Postgres store is unreachable.
    try:
        await cache_service.initialize()
    except Exception as e:
        struct_logger.warning("cache_initialization_failed", error=str(e))

    try:
        # Pre-warm the checkpointer so the first crawl does not pay pool setup.
        await get_checkpointer()
    except Exception as e:
        struct_logger.warning(
            "agent_checkpointer_unavailable",
            error=str(e),
            hint="start the agent store with: docker compose up -d agent-db",
        )

    if agent_settings.AUTH_ENABLED:
        try:
            from app.core.db import database_service

            await database_service.create_tables()
        except Exception as e:
            struct_logger.error("agent_auth_tables_unavailable", error=str(e))

    struct_logger.info(
        "application_startup",
        project=agent_settings.PROJECT_NAME,
        environment=agent_settings.ENVIRONMENT.value,
        auth_enabled=agent_settings.AUTH_ENABLED,
        long_term_memory=agent_settings.LONG_TERM_MEMORY_ENABLED,
        langfuse_tracing=agent_settings.LANGFUSE_TRACING_ENABLED,
    )
    yield

    # Flush before closing anything else: Langfuse exports spans in the
    # background, so a shutdown right after an agent run would drop its tail.
    flush_langfuse()
    await cache_service.close()
    await close_connection_pool()
    struct_logger.info("application_shutdown")


app = FastAPI(title="JobMatcher API", lifespan=lifespan)


# Exception handlers
@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "error": {"code": exc.code, "message": exc.message},
            "pagination": None,
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    logger.exception("Unexpected error")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "error": {"code": "INTERNAL_ERROR", "message": "服务器内部错误"},
            "pagination": None,
        },
    )


# Mount routers
app.include_router(companies.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(favorites.router, prefix="/api")
app.include_router(resume.router, prefix="/api")
app.include_router(match.router, prefix="/api")
app.include_router(compare.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(crawl.router, prefix="/api")
app.include_router(settings.router, prefix="/api")

# Agent framework auth router — only mounted when AUTH_ENABLED is true, so the
# default deployment exposes no new endpoints. Business routes above never
# require a token either way.
if agent_settings.AUTH_ENABLED:
    from app.api.v1 import api_router as agent_api_router

    app.include_router(agent_api_router, prefix=agent_settings.API_V1_STR)

# Prometheus metrics at /metrics, plus per-request duration/count tracking.
setup_metrics(app)
app.add_middleware(MetricsMiddleware)
app.add_middleware(LoggingContextMiddleware)
app.add_middleware(CorrelationIdMiddleware)

# Rate limiting. Only routes carrying an explicit @limiter.limit() decorator are
# limited — no SlowAPIMiddleware is installed — so existing business endpoints
# (including the 3s /api/companies poll from the settings page) are unaffected.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # pyright: ignore[reportArgumentType]


# Read-only demo mode (activated via READ_ONLY_MODE env var).
# Registered before CORS so CORS headers still land on 403 responses.
app.add_middleware(ReadOnlyMiddleware)

# CORS — configured after lifespan sets up config, so use permissive defaults
# The actual origins are set in lifespan via config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
