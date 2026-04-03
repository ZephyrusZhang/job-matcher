from fastapi import APIRouter, Depends, UploadFile, File

import aiosqlite

from app.dependencies import get_database, get_resume_service
from app.schemas.common import ApiResponse
from app.services.resume_service import ResumeService

router = APIRouter(tags=["resume"])


@router.post("/resume/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db: aiosqlite.Connection = Depends(get_database),
    service: ResumeService = Depends(get_resume_service),
):
    result = await service.upload(db, file)
    return ApiResponse.ok(data=result.model_dump())


@router.get("/resume")
async def get_resume(
    db: aiosqlite.Connection = Depends(get_database),
    service: ResumeService = Depends(get_resume_service),
):
    resume = await service.get(db)
    return ApiResponse.ok(data=resume.model_dump() if resume else None)


@router.delete("/resume")
async def delete_resume(
    db: aiosqlite.Connection = Depends(get_database),
    service: ResumeService = Depends(get_resume_service),
):
    result = await service.delete(db)
    return ApiResponse.ok(data={"cleared": result.model_dump()})
