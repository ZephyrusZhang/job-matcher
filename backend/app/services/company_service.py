import aiosqlite

from app.exceptions import CompanyExistsError, CompanyNotFoundError
from app.models import company as company_model
from app.models import job as job_model
from app.schemas.company import CompanyCreate, CompanyOut, CompanyUpdate


class CompanyService:
    def __init__(self):
        self._cache: dict[str, dict] = {}

    async def refresh_cache(self, db: aiosqlite.Connection) -> None:
        rows = await company_model.get_all_companies(db)
        self._cache = {r["id"]: r for r in rows}

    def get_company_name(self, company_id: str) -> str | None:
        company = self._cache.get(company_id)
        return company["name"] if company else None

    def get_company_career_url(self, company_id: str) -> str | None:
        company = self._cache.get(company_id)
        return company["career_url"] if company else None

    def has_company(self, company_id: str) -> bool:
        return company_id in self._cache

    async def get_all(self, db: aiosqlite.Connection) -> list[CompanyOut]:
        rows = await company_model.get_all_companies(db)
        result = []
        for row in rows:
            job_count = await job_model.get_job_count_by_company(db, row["id"])
            last_crawled = await job_model.get_last_crawled_at(db, row["id"])
            crawl_status = await self._get_crawl_status(db, row["id"])
            result.append(
                CompanyOut(
                    id=row["id"],
                    name=row["name"],
                    career_url=row["career_url"],
                    crawl_interval_hours=row["crawl_interval_hours"],
                    last_crawled_at=last_crawled,
                    job_count=job_count,
                    crawl_status=crawl_status,
                )
            )
        return result

    async def create(
        self, db: aiosqlite.Connection, data: CompanyCreate
    ) -> CompanyOut:
        if await company_model.company_exists(db, data.id):
            raise CompanyExistsError()
        row = await company_model.create_company(
            db, data.id, data.name, data.career_url, data.crawl_interval_hours
        )
        self._cache[data.id] = row
        return CompanyOut(
            id=row["id"],
            name=row["name"],
            career_url=row["career_url"],
            crawl_interval_hours=row["crawl_interval_hours"],
        )

    async def update(
        self, db: aiosqlite.Connection, company_id: str, data: CompanyUpdate
    ) -> CompanyOut:
        if not await company_model.company_exists(db, company_id):
            raise CompanyNotFoundError()
        row = await company_model.update_company(
            db, company_id, data.name, data.career_url, data.crawl_interval_hours
        )
        if row:
            self._cache[company_id] = row
        job_count = await job_model.get_job_count_by_company(db, company_id)
        last_crawled = await job_model.get_last_crawled_at(db, company_id)
        crawl_status = await self._get_crawl_status(db, company_id)
        return CompanyOut(
            id=row["id"],
            name=row["name"],
            career_url=row["career_url"],
            crawl_interval_hours=row["crawl_interval_hours"],
            last_crawled_at=last_crawled,
            job_count=job_count,
            crawl_status=crawl_status,
        )

    async def delete(self, db: aiosqlite.Connection, company_id: str) -> None:
        if not await company_model.company_exists(db, company_id):
            raise CompanyNotFoundError()
        await company_model.delete_company(db, company_id)
        self._cache.pop(company_id, None)

    async def _get_crawl_status(
        self, db: aiosqlite.Connection, company_id: str
    ) -> str:
        async with db.execute(
            """SELECT status FROM crawl_tasks
               WHERE company_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (company_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return "idle"
            status = row[0]
            if status in ("pending", "running"):
                return status
            return status  # completed / failed
