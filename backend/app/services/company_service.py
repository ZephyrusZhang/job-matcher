import json

import aiosqlite

from app.config import CompanyConfig
from app.models import job as job_model
from app.schemas.company import CompanyOut


class CompanyService:
    def __init__(self, companies: list[CompanyConfig]):
        self._companies = {c.id: c for c in companies}

    async def get_all(self, db: aiosqlite.Connection) -> list[CompanyOut]:
        result = []
        for company in self._companies.values():
            job_count = await job_model.get_job_count_by_company(db, company.id)
            last_crawled = await job_model.get_last_crawled_at(db, company.id)
            result.append(
                CompanyOut(
                    id=company.id,
                    name=company.name,
                    career_url=company.career_url,
                    crawl_interval_hours=company.crawl_interval_hours,
                    last_crawled_at=last_crawled,
                    job_count=job_count,
                )
            )
        return result

    def get_company_name(self, company_id: str) -> str | None:
        company = self._companies.get(company_id)
        return company.name if company else None

    def get_company(self, company_id: str) -> CompanyConfig | None:
        return self._companies.get(company_id)
