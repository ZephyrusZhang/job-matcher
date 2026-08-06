from fastapi import APIRouter, Depends

import aiosqlite

from app.dependencies import get_company_service, get_database, get_job_service
from app.exceptions import CrawlInProgressError
from app.models import crawl_task as task_model
from app.models import crawler_script as script_model
from app.schemas.common import ApiResponse
from app.schemas.company import CompanyCreate, CompanyUpdate
from app.schemas.crawler_script import CrawlerScriptUpdate
from app.services.company_service import CompanyService
from app.services.job_service import JobService

router = APIRouter(tags=["companies"])


@router.get("/companies")
async def list_companies(
    db: aiosqlite.Connection = Depends(get_database),
    service: CompanyService = Depends(get_company_service),
):
    companies = await service.get_all(db)
    return ApiResponse.ok(data=[c.model_dump() for c in companies])


@router.post("/companies", status_code=201)
async def create_company(
    body: CompanyCreate,
    db: aiosqlite.Connection = Depends(get_database),
    service: CompanyService = Depends(get_company_service),
):
    company = await service.create(db, body)
    return ApiResponse.ok(data=company.model_dump())


@router.put("/companies/{company_id}")
async def update_company(
    company_id: str,
    body: CompanyUpdate,
    db: aiosqlite.Connection = Depends(get_database),
    service: CompanyService = Depends(get_company_service),
):
    company = await service.update(db, company_id, body)
    return ApiResponse.ok(data=company.model_dump())


@router.delete("/companies/{company_id}")
async def delete_company(
    company_id: str,
    db: aiosqlite.Connection = Depends(get_database),
    service: CompanyService = Depends(get_company_service),
):
    await service.delete(db, company_id)
    return ApiResponse.ok(data=None)


@router.delete("/companies/{company_id}/jobs")
async def clear_company_jobs(
    company_id: str,
    db: aiosqlite.Connection = Depends(get_database),
    service: JobService = Depends(get_job_service),
):
    """Delete every crawled job of a company, keeping the company itself.

    Refused while a crawl is running: ``store_jobs`` would be inserting rows
    into the table this is emptying, and the user would be left with whichever
    half of the batch happened to land after the DELETE.
    """
    if await task_model.has_active_task(db, company_id):
        raise CrawlInProgressError()

    jobs, favorites = await service.clear_company_jobs(db, company_id)
    return ApiResponse.ok(data={"deleted_jobs": jobs, "deleted_favorites": favorites})


# ── Crawler Script endpoints ──


@router.get("/companies/{company_id}/crawler-script")
async def get_crawler_script(
    company_id: str,
    db: aiosqlite.Connection = Depends(get_database),
):
    row = await script_model.get_script(db, company_id)
    if not row:
        return ApiResponse.ok(data=None)
    return ApiResponse.ok(data={
        "company_id": row["company_id"],
        "code": row["code"],
        "updated_at": row["updated_at"],
    })


@router.put("/companies/{company_id}/crawler-script")
async def update_crawler_script(
    company_id: str,
    body: CrawlerScriptUpdate,
    db: aiosqlite.Connection = Depends(get_database),
):
    row = await script_model.upsert_script(db, company_id, body.code)
    return ApiResponse.ok(data={
        "company_id": row["company_id"],
        "code": row["code"],
        "updated_at": row["updated_at"],
    })


@router.delete("/companies/{company_id}/crawler-script")
async def delete_crawler_script(
    company_id: str,
    db: aiosqlite.Connection = Depends(get_database),
):
    await script_model.delete_script(db, company_id)
    return ApiResponse.ok(data=None)
