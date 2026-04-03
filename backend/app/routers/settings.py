from fastapi import APIRouter, Depends

import aiosqlite

from app.dependencies import get_database, get_settings_service
from app.schemas.common import ApiResponse
from app.services.settings_service import SettingsService

router = APIRouter(tags=["settings"])


class SettingsUpdate:
    """Using a simple dict for flexibility."""
    pass


@router.get("/settings")
async def get_settings(
    db: aiosqlite.Connection = Depends(get_database),
    service: SettingsService = Depends(get_settings_service),
):
    settings = await service.get(db)
    return ApiResponse.ok(data=settings)


@router.patch("/settings")
async def update_settings(
    body: dict,
    db: aiosqlite.Connection = Depends(get_database),
    service: SettingsService = Depends(get_settings_service),
):
    settings = await service.update(
        db,
        display_density=body.get("display_density"),
        language=body.get("language"),
    )
    return ApiResponse.ok(data=settings)
