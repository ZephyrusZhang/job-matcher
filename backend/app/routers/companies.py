from fastapi import APIRouter, Depends

import aiosqlite

from app.dependencies import get_company_service, get_database
from app.models import crawler_script as script_model
from app.schemas.common import ApiResponse
from app.schemas.company import CompanyCreate, CompanyUpdate
from app.schemas.crawler_script import CrawlerScriptUpdate
from app.services.company_service import CompanyService

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
