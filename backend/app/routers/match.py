"""Conversational job matching endpoints.

Replaces the previous one-shot report generator: `/match` is now a chat page,
so the API is conversation-oriented and the single streaming endpoint carries a
tool timeline alongside the answer.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

import aiosqlite

from app.dependencies import get_database, get_match_service
from app.schemas.common import ApiResponse
from app.schemas.match import (
    ConversationCreate,
    ConversationUpdate,
    SendMessageRequest,
)
from app.services.match_service import MatchService

router = APIRouter(tags=["match"])


@router.post("/match/conversations", status_code=201)
async def create_conversation(
    body: ConversationCreate,
    db: aiosqlite.Connection = Depends(get_database),
    service: MatchService = Depends(get_match_service),
):
    """Start a new conversation."""
    conversation = await service.create_conversation(db, body.title)
    return ApiResponse.ok(data=conversation.model_dump())


@router.get("/match/conversations")
async def list_conversations(
    db: aiosqlite.Connection = Depends(get_database),
    service: MatchService = Depends(get_match_service),
):
    """List every conversation, most recently used first."""
    conversations = await service.list_conversations(db)
    return ApiResponse.ok(data=[c.model_dump() for c in conversations])


@router.patch("/match/conversations/{session_id}")
async def rename_conversation(
    session_id: str,
    body: ConversationUpdate,
    db: aiosqlite.Connection = Depends(get_database),
    service: MatchService = Depends(get_match_service),
):
    """Rename a conversation."""
    conversation = await service.rename_conversation(db, session_id, body.title)
    return ApiResponse.ok(data=conversation.model_dump())


@router.delete("/match/conversations/{session_id}")
async def delete_conversation(
    session_id: str,
    db: aiosqlite.Connection = Depends(get_database),
    service: MatchService = Depends(get_match_service),
):
    """Delete a conversation, its messages, and its agent checkpoints."""
    await service.delete_conversation(db, session_id)
    return ApiResponse.ok(data=None)


@router.get("/match/conversations/{session_id}/messages")
async def list_messages(
    session_id: str,
    db: aiosqlite.Connection = Depends(get_database),
    service: MatchService = Depends(get_match_service),
):
    """Return a conversation's message history."""
    messages = await service.list_messages(db, session_id)
    return ApiResponse.ok(data=[m.model_dump() for m in messages])


@router.post("/match/conversations/{session_id}/messages")
async def send_message(
    session_id: str,
    body: SendMessageRequest,
    db: aiosqlite.Connection = Depends(get_database),
    service: MatchService = Depends(get_match_service),
):
    """Send a message and stream the agent's turn back as SSE."""
    return StreamingResponse(
        service.stream_turn(db, session_id, body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
