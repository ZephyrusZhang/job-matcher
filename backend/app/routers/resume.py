from fastapi import APIRouter, Depends, File, Form, UploadFile

import aiosqlite

from app.dependencies import get_database, get_resume_service
from app.schemas.common import ApiResponse
from app.schemas.resume import ResumeUpdate
from app.services.resume_service import ResumeService

router = APIRouter(tags=["resume"])


# ── Collection API ────────────────────────────────────────────────────────


@router.get("/resumes")
async def list_resumes(
    db: aiosqlite.Connection = Depends(get_database),
    service: ResumeService = Depends(get_resume_service),
):
    """List every stored resume, default first."""
    resumes = await service.list(db)
    return ApiResponse.ok(data=[r.model_dump() for r in resumes])


@router.post("/resumes")
async def create_resume(
    file: UploadFile = File(...),
    label: str = Form(""),
    make_default: bool = Form(False),
    db: aiosqlite.Connection = Depends(get_database),
    service: ResumeService = Depends(get_resume_service),
):
    """Upload a new resume."""
    result = await service.upload(db, file, label=label, make_default=make_default)
    return ApiResponse.ok(data=result.model_dump())


@router.patch("/resumes/{resume_id}")
async def update_resume(
    resume_id: str,
    body: ResumeUpdate,
    db: aiosqlite.Connection = Depends(get_database),
    service: ResumeService = Depends(get_resume_service),
):
    """Rename a resume and/or make it the default."""
    result = await service.update(db, resume_id, label=body.label, is_default=body.is_default)
    return ApiResponse.ok(data=result.model_dump())


@router.delete("/resumes/{resume_id}")
async def delete_resume_by_id(
    resume_id: str,
    db: aiosqlite.Connection = Depends(get_database),
    service: ResumeService = Depends(get_resume_service),
):
    """Delete one resume."""
    await service.delete(db, resume_id)
    return ApiResponse.ok(data=None)


# ── Singleton shortcuts for the default resume ────────────────────────────


@router.post("/resume/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db: aiosqlite.Connection = Depends(get_database),
    service: ResumeService = Depends(get_resume_service),
):
    """Upload a resume and make it the default."""
    result = await service.upload(db, file, make_default=True)
    return ApiResponse.ok(data=result.model_dump())


@router.get("/resume")
async def get_resume(
    db: aiosqlite.Connection = Depends(get_database),
    service: ResumeService = Depends(get_resume_service),
):
    """Return the default resume."""
    resume = await service.get(db)
    return ApiResponse.ok(data=resume.model_dump() if resume else None)


@router.delete("/resume")
async def delete_resume(
    db: aiosqlite.Connection = Depends(get_database),
    service: ResumeService = Depends(get_resume_service),
):
    """Delete the default resume."""
    await service.delete(db)
    return ApiResponse.ok(data=None)
