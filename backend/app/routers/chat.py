from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

import aiosqlite

from app.dependencies import get_chat_service, get_database
from app.schemas.chat import ChatMessageRequest
from app.schemas.common import ApiResponse
from app.services.chat_service import ChatService

router = APIRouter(tags=["chat"])


@router.post("/chat/message")
async def send_message(
    body: ChatMessageRequest,
    db: aiosqlite.Connection = Depends(get_database),
    service: ChatService = Depends(get_chat_service),
):
    return StreamingResponse(
        service.send_message(db, body.report_id, body.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/history")
async def get_chat_history(
    report_id: str,
    db: aiosqlite.Connection = Depends(get_database),
    service: ChatService = Depends(get_chat_service),
):
    history = await service.get_history(db, report_id)
    return ApiResponse.ok(data=history.model_dump())
