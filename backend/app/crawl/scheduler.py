"""APScheduler-based crawl scheduling."""

import logging
from collections.abc import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import CompanyConfig

logger = logging.getLogger(__name__)


class CrawlScheduler:
    def __init__(self, companies: list[CompanyConfig]):
        self._companies = companies
        self._scheduler = AsyncIOScheduler()

    def start(self, crawl_func: Callable):
        """Register interval jobs for each company and start the scheduler."""
        for company in self._companies:
            self._scheduler.add_job(
                crawl_func,
                "interval",
                hours=company.crawl_interval_hours,
                args=[company],
                id=f"crawl_{company.id}",
                replace_existing=True,
            )
            logger.info(
                "Scheduled crawl for %s every %dh",
                company.name,
                company.crawl_interval_hours,
            )
        self._scheduler.start()

    def stop(self):
        """Shutdown the scheduler."""
        self._scheduler.shutdown(wait=False)

    async def trigger_manual(self, company_id: str, crawl_func: Callable):
        """Manually trigger a crawl for a specific company."""
        company = next((c for c in self._companies if c.id == company_id), None)
        if company:
            await crawl_func(company)
