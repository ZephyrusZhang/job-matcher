from fastapi import APIRouter, Depends

import aiosqlite

from app.dependencies import get_database, get_favorite_service
from app.schemas.common import ApiResponse
from app.schemas.favorite import FavoriteCreate
from app.services.favorite_service import FavoriteService

router = APIRouter(tags=["favorites"])


@router.post("/favorites", status_code=201)
async def add_favorite(
    body: FavoriteCreate,
    db: aiosqlite.Connection = Depends(get_database),
    service: FavoriteService = Depends(get_favorite_service),
):
    result = await service.add_favorite(db, body.job_id)
    return ApiResponse.ok(data=result.model_dump())


@router.delete("/favorites/{job_id}")
async def remove_favorite(
    job_id: str,
    db: aiosqlite.Connection = Depends(get_database),
    service: FavoriteService = Depends(get_favorite_service),
):
    await service.remove_favorite(db, job_id)
    return ApiResponse.ok()


@router.get("/favorites")
async def list_favorites(
    company_id: str | None = None,
    db: aiosqlite.Connection = Depends(get_database),
    service: FavoriteService = Depends(get_favorite_service),
):
    favorites = await service.get_favorites(db, company_id)
    return ApiResponse.ok(data=[f.model_dump() for f in favorites])


@router.get("/favorites/summary")
async def favorites_summary(
    db: aiosqlite.Connection = Depends(get_database),
    service: FavoriteService = Depends(get_favorite_service),
):
    summary = await service.get_summary(db)
    return ApiResponse.ok(data=[s.model_dump() for s in summary])
