"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import AppConfig, load_config
from app.database import Database
from app.exceptions import JobNotFoundError, register_exception_handlers


def create_app(
    config: AppConfig | None = None,
    database: Database | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    if config is None:
        config = load_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal database
        if database is None:
            database = Database(config.database)
            await database.init()

        app.state.config = config
        app.state.db = database

        yield

        if database:
            await database.close()

    app = FastAPI(title="JobMatcher API", lifespan=lifespan)

    register_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.server.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store references for non-lifespan access
    app.state.config = config
    if database:
        app.state.db = database

    # Register routers
    _register_routers(app)

    return app


def _register_routers(app: FastAPI):
    """Register all API routers."""
    from app.routers import jobs

    app.include_router(jobs.router, prefix="/api")

    # Test-only route for exception middleware testing
    from fastapi import APIRouter

    test_router = APIRouter(prefix="/api/_test", tags=["test"])

    @test_router.get("/error")
    async def trigger_error():
        raise RuntimeError("Intentional test error")

    app.include_router(test_router)
