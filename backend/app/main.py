import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import load_config
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

logging.basicConfig(level=logging.INFO)
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

    logger.info("JobMatcher API started")
    yield
    logger.info("JobMatcher API shutting down")


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
