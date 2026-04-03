from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

import aiosqlite

from app.dependencies import get_database, get_report_service
from app.schemas.common import ApiResponse
from app.schemas.report import GenerateRequest
from app.services.report_service import ReportService

router = APIRouter(tags=["match"])


@router.post("/match/generate")
async def generate_match_report(
    body: GenerateRequest,
    db: aiosqlite.Connection = Depends(get_database),
    service: ReportService = Depends(get_report_service),
):
    return StreamingResponse(
        service.generate_report(db, body.company_id, body.preferences, "match"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/match/report")
async def get_match_report(
    company_id: str,
    db: aiosqlite.Connection = Depends(get_database),
    service: ReportService = Depends(get_report_service),
):
    report = await service.get_report(db, company_id, "match")
    return ApiResponse.ok(data=report.model_dump() if report else None)
