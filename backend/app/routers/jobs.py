from fastapi import APIRouter, Depends, Query

import aiosqlite

from app.dependencies import get_database, get_job_service
from app.schemas.common import ApiResponse
from app.services.job_service import JobService

router = APIRouter(tags=["jobs"])


@router.get("/jobs")
async def list_jobs(
    company_id: str,
    category: str | None = None,
    location: str | None = None,
    job_type: str | None = None,
    posted_within: str | None = None,
    sort_by: str = "posted_date",
    sort_order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: aiosqlite.Connection = Depends(get_database),
    service: JobService = Depends(get_job_service),
):
    jobs, pagination = await service.get_jobs(
        db, company_id, category, location, job_type,
        posted_within, sort_by, sort_order, page, page_size,
    )
    return ApiResponse.ok(
        data=[j.model_dump() for j in jobs],
        pagination=pagination,
    )


@router.get("/jobs/search")
async def search_jobs(
    q: str,
    company_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: aiosqlite.Connection = Depends(get_database),
    service: JobService = Depends(get_job_service),
):
    jobs, pagination = await service.search_jobs(db, q, company_id, page, page_size)
    return ApiResponse.ok(
        data=[j.model_dump() for j in jobs],
        pagination=pagination,
    )


@router.get("/jobs/locations")
async def list_job_locations(
    company_id: str,
    db: aiosqlite.Connection = Depends(get_database),
    service: JobService = Depends(get_job_service),
):
    """Return the deduplicated, sorted list of cities present in a company's jobs.

    Used by the frontend's location filter dropdown.
    """
    locations = await service.get_locations(db, company_id)
    return ApiResponse.ok(data=locations)


@router.get("/jobs/suggest")
async def suggest_jobs(
    q: str,
    limit: int = Query(5, ge=1, le=20),
    db: aiosqlite.Connection = Depends(get_database),
    service: JobService = Depends(get_job_service),
):
    suggestions = await service.suggest(db, q, limit)
    return ApiResponse.ok(data=suggestions)


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    db: aiosqlite.Connection = Depends(get_database),
    service: JobService = Depends(get_job_service),
):
    job = await service.get_job_by_id(db, job_id)
    return ApiResponse.ok(data=job.model_dump())
