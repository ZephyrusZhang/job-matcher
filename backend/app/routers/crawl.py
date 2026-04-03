from fastapi import APIRouter, Depends, Query

import aiosqlite

from app.dependencies import get_crawl_service, get_database
from app.schemas.common import ApiResponse
from app.schemas.crawl import CrawlTriggerRequest
from app.services.crawl_service import CrawlService

router = APIRouter(tags=["crawl"])


@router.post("/crawl/trigger", status_code=201)
async def trigger_crawl(
    body: CrawlTriggerRequest,
    db: aiosqlite.Connection = Depends(get_database),
    service: CrawlService = Depends(get_crawl_service),
):
    task = await service.trigger(db, body.company_id)
    return ApiResponse.ok(data=task.model_dump())


@router.get("/crawl/tasks")
async def list_crawl_tasks(
    company_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: aiosqlite.Connection = Depends(get_database),
    service: CrawlService = Depends(get_crawl_service),
):
    tasks, pagination = await service.get_tasks(db, company_id, page, page_size)
    return ApiResponse.ok(
        data=[t.model_dump() for t in tasks],
        pagination=pagination,
    )


@router.post("/crawl/tasks/{task_id}/cancel")
async def cancel_crawl_task(
    task_id: str,
    db: aiosqlite.Connection = Depends(get_database),
    service: CrawlService = Depends(get_crawl_service),
):
    task = await service.cancel(db, task_id)
    return ApiResponse.ok(data=task.model_dump())


@router.get("/crawl/tasks/{task_id}")
async def get_crawl_task(
    task_id: str,
    db: aiosqlite.Connection = Depends(get_database),
    service: CrawlService = Depends(get_crawl_service),
):
    task = await service.get_task_by_id(db, task_id)
    if not task:
        return ApiResponse.error_response("NOT_FOUND", "任务不存在")
    return ApiResponse.ok(data=task.model_dump())
