import asyncio
import logging
import math
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import aiosqlite

from app.config import AppConfig
from app.crawl.pipeline import run_cached_crawler, run_crawler, store_jobs
from app.database import get_db
from app.exceptions import AppError, CompanyNotFoundError, CrawlInProgressError
from app.models import crawl_task as task_model
from app.models import crawler_script as script_model
from app.schemas.common import PaginationMeta
from app.schemas.crawl import CrawlTaskOut
from app.services.company_service import CompanyService

logger = logging.getLogger(__name__)

# Thread pool for running the blocking AgentRunner
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="crawl")


class CrawlService:
    def __init__(self, company_service: CompanyService, config: AppConfig):
        self.company_service = company_service
        self.config = config
        self._cancel_events: dict[str, threading.Event] = {}

    async def trigger(
        self, db: aiosqlite.Connection, company_id: str
    ) -> CrawlTaskOut:
        if await task_model.has_active_task(db, company_id):
            raise CrawlInProgressError()

        if not self.company_service.has_company(company_id):
            raise CompanyNotFoundError()

        career_url = self.company_service.get_company_career_url(company_id)
        if not career_url:
            raise CompanyNotFoundError()

        # Check for cached crawler script
        script_row = await script_model.get_script(db, company_id)
        cached_code = script_row["code"] if script_row else None
        logger.info(
            f"Trigger crawl: company={company_id}, "
            f"cached_code={'yes (' + str(len(cached_code)) + ' chars)' if cached_code else 'no'}"
        )

        task_id = str(uuid.uuid4())
        await task_model.create_task(db, task_id, company_id)

        cancel_event = threading.Event()
        self._cancel_events[task_id] = cancel_event

        asyncio.get_event_loop().run_in_executor(
            _executor,
            self._run_crawl_sync,
            task_id,
            company_id,
            career_url,
            self.config.database.path,
            cancel_event,
            cached_code,
        )

        task = await task_model.get_task_by_id(db, task_id)
        return self._task_to_out(task)

    async def cancel(self, db: aiosqlite.Connection, task_id: str) -> CrawlTaskOut:
        task = await task_model.get_task_by_id(db, task_id)
        if not task:
            raise AppError("NOT_FOUND", "任务不存在", 404)

        if task["status"] not in ("pending", "running"):
            raise AppError("INVALID_STATUS", "只能取消进行中的任务", 400)

        cancel_event = self._cancel_events.get(task_id)
        if cancel_event:
            cancel_event.set()

        await task_model.update_task_status(
            db, task_id, "cancelled",
            error_message="用户手动取消",
        )

        task = await task_model.get_task_by_id(db, task_id)
        return self._task_to_out(task)

    def _run_crawl_sync(
        self,
        task_id: str,
        company_id: str,
        career_url: str,
        db_path: str,
        cancel_event: threading.Event,
        cached_code: str | None,
    ) -> None:
        try:
            asyncio.run(
                self._run_crawl(task_id, company_id, career_url, db_path, cancel_event, cached_code)
            )
        finally:
            self._cancel_events.pop(task_id, None)

    async def _run_crawl(
        self,
        task_id: str,
        company_id: str,
        career_url: str,
        db_path: str,
        cancel_event: threading.Event,
        cached_code: str | None,
    ) -> None:
        db = await get_db(db_path)
        try:
            if cancel_event.is_set():
                return

            await task_model.update_task_status(db, task_id, "running")

            loop = asyncio.get_event_loop()
            raw_jobs: list[dict] = []
            new_code: str | None = None

            cache_hit = False

            if cached_code:
                # Try cached code first
                logger.info(f"[crawl] Using cached code for company={company_id} ({len(cached_code)} chars)")
                try:
                    raw_jobs = await loop.run_in_executor(
                        None, run_cached_crawler, cached_code, cancel_event
                    )
                    cache_hit = True
                    logger.info(f"[crawl] Cached crawler succeeded: {len(raw_jobs)} jobs")
                except Exception as e:
                    logger.warning(f"[crawl] Cached crawler FAILED for company={company_id}: {e}")
            else:
                logger.info(f"[crawl] No cached code for company={company_id}")

            if not cache_hit and not cancel_event.is_set():
                # No cached code, or cached code failed → run full agent
                logger.info(f"Running agent crawler for company={company_id}")
                raw_jobs, new_code = await loop.run_in_executor(
                    None, run_crawler, career_url, cancel_event
                )

                # Cache the generated code on success
                if new_code and raw_jobs and not cancel_event.is_set():
                    await script_model.upsert_script(db, company_id, new_code)
                    logger.info(f"Cached crawler script for company={company_id}")

            if cancel_event.is_set():
                logger.info(f"Crawl cancelled after crawl phase: task={task_id}")
                return

            jobs_found, jobs_new, jobs_updated = await store_jobs(
                db, raw_jobs, company_id, cancel_event
            )

            status = "cancelled" if cancel_event.is_set() else "completed"
            await task_model.update_task_status(
                db, task_id, status,
                jobs_found=jobs_found,
                jobs_new=jobs_new,
                jobs_updated=jobs_updated,
                error_message="用户手动取消" if cancel_event.is_set() else None,
            )
            logger.info(
                f"Crawl {status}: company={company_id}, "
                f"found={jobs_found}, new={jobs_new}, updated={jobs_updated}"
            )

        except Exception as e:
            if cancel_event.is_set():
                logger.info(f"Crawl cancelled with error: task={task_id}")
                return
            logger.exception(f"Crawl failed: company={company_id}")
            await task_model.update_task_status(
                db, task_id, "failed",
                error_message=str(e)[:500],
            )
        finally:
            await db.close()

    def _task_to_out(self, row: dict) -> CrawlTaskOut:
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

    async def get_tasks(
        self,
        db: aiosqlite.Connection,
        company_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CrawlTaskOut], PaginationMeta]:
        rows, total = await task_model.get_tasks(db, company_id, page, page_size)
        tasks = [self._task_to_out(row) for row in rows]
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
        return self._task_to_out(row)
