from fastapi import APIRouter, Depends

import aiosqlite

from app.dependencies import get_company_service, get_database
from app.schemas.common import ApiResponse
from app.services.company_service import CompanyService

router = APIRouter(tags=["companies"])


@router.get("/companies")
async def list_companies(
    db: aiosqlite.Connection = Depends(get_database),
    service: CompanyService = Depends(get_company_service),
):
    companies = await service.get_all(db)
    return ApiResponse.ok(data=[c.model_dump() for c in companies])
