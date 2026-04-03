import math
import uuid

import aiosqlite

from app.exceptions import CrawlInProgressError
from app.models import crawl_task as task_model
from app.schemas.common import PaginationMeta
from app.schemas.crawl import CrawlTaskOut
from app.services.company_service import CompanyService


class CrawlService:
    def __init__(self, company_service: CompanyService):
        self.company_service = company_service

    async def trigger(
        self, db: aiosqlite.Connection, company_id: str
    ) -> CrawlTaskOut:
        # Check for active task
        if await task_model.has_active_task(db, company_id):
            raise CrawlInProgressError()

        task_id = str(uuid.uuid4())
        await task_model.create_task(db, task_id, company_id)

        company_name = self.company_service.get_company_name(company_id) or company_id

        # Get created task
        task = await task_model.get_task_by_id(db, task_id)
        return CrawlTaskOut(
            id=task["id"],
            company_id=task["company_id"],
            company_name=company_name,
            status=task["status"],
            jobs_found=task["jobs_found"] or 0,
            jobs_new=task["jobs_new"] or 0,
            jobs_updated=task["jobs_updated"] or 0,
            error_message=task.get("error_message"),
            started_at=task.get("started_at"),
            completed_at=task.get("completed_at"),
            created_at=task["created_at"],
        )

    async def get_tasks(
        self,
        db: aiosqlite.Connection,
        company_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CrawlTaskOut], PaginationMeta]:
        rows, total = await task_model.get_tasks(db, company_id, page, page_size)
        tasks = []
        for row in rows:
            company_name = self.company_service.get_company_name(row["company_id"]) or row["company_id"]
            tasks.append(
                CrawlTaskOut(
                    id=row["id"],
                    company_id=row["company_id"],
                    company_name=company_name,
                    status=row["status"],
                    jobs_found=row["jobs_found"] or 0,
                    jobs_new=row["jobs_new"] or 0,
                    jobs_updated=row["jobs_updated"] or 0,
                    error_message=row.get("error_message"),
                    started_at=row.get("started_at"),
                    completed_at=row.get("completed_at"),
                    created_at=row["created_at"],
                )
            )
        pagination = PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if page_size > 0 else 0,
        )
        return tasks, pagination

    async def get_task_by_id(
        self, db: aiosqlite.Connection, task_id: str
    ) -> CrawlTaskOut | None:
        row = await task_model.get_task_by_id(db, task_id)
        if not row:
            return None
        company_name = self.company_service.get_company_name(row["company_id"]) or row["company_id"]
        return CrawlTaskOut(
            id=row["id"],
            company_id=row["company_id"],
            company_name=company_name,
            status=row["status"],
            jobs_found=row["jobs_found"] or 0,
            jobs_new=row["jobs_new"] or 0,
            jobs_updated=row["jobs_updated"] or 0,
            error_message=row.get("error_message"),
            started_at=row.get("started_at"),
            completed_at=row.get("completed_at"),
            created_at=row["created_at"],
        )
