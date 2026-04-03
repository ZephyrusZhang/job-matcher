"""FastAPI dependency injection."""
from typing import AsyncGenerator

import aiosqlite

from app.config import AppConfig
from app.database import get_db
from app.llm.client import LLMClient
from app.services.chat_service import ChatService
from app.services.company_service import CompanyService
from app.services.crawl_service import CrawlService
from app.services.favorite_service import FavoriteService
from app.services.job_service import JobService
from app.services.report_service import ReportService
from app.services.resume_service import ResumeService
from app.services.settings_service import SettingsService

# Global singletons, initialized in lifespan
_config: AppConfig | None = None
_llm_client: LLMClient | None = None
_company_service: CompanyService | None = None
_job_service: JobService | None = None
_favorite_service: FavoriteService | None = None
_resume_service: ResumeService | None = None
_report_service: ReportService | None = None
_chat_service: ChatService | None = None
_crawl_service: CrawlService | None = None
_settings_service: SettingsService | None = None


async def init_services(config: AppConfig, db_path: str) -> None:
    """Initialize all service singletons."""
    global _config, _llm_client, _company_service, _job_service
    global _favorite_service, _resume_service, _report_service
    global _chat_service, _crawl_service, _settings_service

    _config = config
    _llm_client = LLMClient(config.llm)
    _company_service = CompanyService()

    # Load company cache from DB
    db = await get_db(db_path)
    try:
        await _company_service.refresh_cache(db)
    finally:
        await db.close()

    _job_service = JobService(_company_service)
    _favorite_service = FavoriteService(_company_service)
    _resume_service = ResumeService(config.uploads, _llm_client)
    _report_service = ReportService(_llm_client)
    _chat_service = ChatService(_llm_client)
    _crawl_service = CrawlService(_company_service, config)
    _settings_service = SettingsService()


async def get_database() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Yield a database connection."""
    db = await get_db(_config.database.path)
    try:
        yield db
    finally:
        await db.close()


def get_company_service() -> CompanyService:
    return _company_service


def get_job_service() -> JobService:
    return _job_service


def get_favorite_service() -> FavoriteService:
    return _favorite_service


def get_resume_service() -> ResumeService:
    return _resume_service


def get_report_service() -> ReportService:
    return _report_service


def get_chat_service() -> ChatService:
    return _chat_service


def get_crawl_service() -> CrawlService:
    return _crawl_service


def get_settings_service() -> SettingsService:
    return _settings_service
