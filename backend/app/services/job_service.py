import json
import math

import aiosqlite

from app.crawl.location import normalize_location
from app.exceptions import JobNotFoundError
from app.models import job as job_model
from app.schemas.common import PaginationMeta
from app.schemas.job import CompanyBrief, JobOut, Requirements
from app.services.company_service import CompanyService


def _parse_location_field(raw: str | None) -> list[str]:
    """Parse a DB location field into a list of cities.

    Handles three forms for backward compatibility:
      - JSON array string: '["北京","上海"]'   (new format)
      - Legacy raw string: "深圳总部 / 北京"   (old format, pre-migration)
      - None / empty
    """
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        stripped = raw.lstrip()
        if stripped.startswith("["):
            try:
                value = json.loads(raw)
                if isinstance(value, list):
                    return [str(v) for v in value if v]
            except json.JSONDecodeError:
                pass
        # Fallback: treat as legacy raw string and normalize on the fly.
        return normalize_location(raw)
    return []


class JobService:
    def __init__(self, company_service: CompanyService):
        self.company_service = company_service

    def _row_to_job(self, row: dict) -> JobOut:
        must_have = row.get("requirements_must", "[]")
        nice_to_have = row.get("requirements_nice", "[]")
        if isinstance(must_have, str):
            must_have = json.loads(must_have) if must_have else []
        if isinstance(nice_to_have, str):
            nice_to_have = json.loads(nice_to_have) if nice_to_have else []

        location = _parse_location_field(row.get("location"))

        company_name = self.company_service.get_company_name(row["company_id"]) or row["company_id"]

        return JobOut(
            id=row["id"],
            title=row["title"],
            category=row["category"],
            company=CompanyBrief(id=row["company_id"], name=company_name),
            location=location,
            job_type=row.get("job_type"),
            responsibilities=row.get("responsibilities"),
            requirements=Requirements(must_have=must_have, nice_to_have=nice_to_have),
            department=row.get("department"),
            department_product=row.get("department_product"),
            education=row.get("education"),
            experience=row.get("experience"),
            posted_date=row.get("posted_date"),
            source_url=row["source_url"],
            summary=row.get("summary"),
            is_favorited=bool(row.get("is_favorited", 0)),
            created_at=row["created_at"],
        )

    async def get_jobs(
        self,
        db: aiosqlite.Connection,
        company_id: str,
        category: str | None = None,
        location: str | None = None,
        job_type: str | None = None,
        posted_within: str | None = None,
        sort_by: str = "posted_date",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[JobOut], PaginationMeta]:
        page_size = min(page_size, 50)
        rows, total = await job_model.get_jobs(
            db, company_id, category, location, job_type,
            posted_within, sort_by, sort_order, page, page_size,
        )
        jobs = [self._row_to_job(row) for row in rows]
        pagination = PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if page_size > 0 else 0,
        )
        return jobs, pagination

    async def get_job_by_id(self, db: aiosqlite.Connection, job_id: str) -> JobOut:
        row = await job_model.get_job_by_id(db, job_id)
        if not row:
            raise JobNotFoundError()
        return self._row_to_job(row)

    async def search_jobs(
        self,
        db: aiosqlite.Connection,
        q: str,
        company_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[JobOut], PaginationMeta]:
        page_size = min(page_size, 50)
        rows, total = await job_model.search_jobs(db, q, company_id, page, page_size)
        jobs = [self._row_to_job(row) for row in rows]
        pagination = PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if page_size > 0 else 0,
        )
        return jobs, pagination

    async def suggest(
        self, db: aiosqlite.Connection, q: str, limit: int = 5
    ) -> list[str]:
        return await job_model.suggest_jobs(db, q, limit)

    async def get_locations(
        self, db: aiosqlite.Connection, company_id: str
    ) -> list[str]:
        """Aggregate the distinct cities across all jobs of a company."""
        rows = await job_model.get_company_location_rows(db, company_id)
        seen: set[str] = set()
        ordered: list[str] = []
        for row in rows:
            for city in _parse_location_field(row.get("location")):
                if city not in seen:
                    seen.add(city)
                    ordered.append(city)
        ordered.sort()
        return ordered
