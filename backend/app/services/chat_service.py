import json
import uuid
from collections.abc import AsyncGenerator

import aiosqlite

from app.exceptions import ReportNotFoundError
from app.llm.client import LLMClient
from app.llm.context import ContextManager
from app.llm.prompts import chat as chat_prompt
from app.models import chat as chat_model
from app.models import favorite as fav_model
from app.models import report as report_model
from app.models import resume as resume_model
from app.schemas.chat import ChatHistoryOut, ChatMessageOut


class ChatService:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.context_manager = ContextManager()

    async def send_message(
        self,
        db: aiosqlite.Connection,
        report_id: str,
        message: str,
    ) -> AsyncGenerator[str, None]:
        """Handle a follow-up chat message, streaming the response."""
        # Validate report exists
        report = await report_model.get_report_by_id(db, report_id)
        if not report:
            raise ReportNotFoundError()

        # Get resume
        resume_data = await resume_model.get_resume(db)
        parsed_resume = json.dumps(
            resume_data["parsed_data"], ensure_ascii=False
        ) if resume_data else "{}"

        # Get favorited jobs for context
        fav_jobs = await fav_model.get_favorite_jobs_by_company(db, report["company_id"])
        jobs_str = self.context_manager.format_jobs_for_context(fav_jobs)

        # Build system message
        prefs_str = json.dumps(report["preferences"], ensure_ascii=False)
        system_msg = chat_prompt.build_system_message(
            parsed_resume=parsed_resume,
            preferences=prefs_str,
            report_content=report["content"],
            jobs_detail=jobs_str,
        )

        # Get chat history
        history = await chat_model.get_chat_history(db, report_id)

        # Build messages with context
        messages = self.context_manager.build_chat_messages(
            system_msg, history, message
        )

        # Save user message
        user_msg_id = str(uuid.uuid4())
        await chat_model.insert_message(db, user_msg_id, report_id, "user", message)

        # Generate response
        message_id = str(uuid.uuid4())
        full_response = []

        # Start event
        yield f"event: chat_start\ndata: {json.dumps({'message_id': message_id})}\n\n"

        # Stream
        async for chunk in self.llm_client.stream_chat(messages):
            full_response.append(chunk)
            yield f"event: chunk\ndata: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"

        # Save assistant message
        response_content = "".join(full_response)
        await chat_model.insert_message(
            db, message_id, report_id, "assistant", response_content
        )

        # End event
        yield f"event: chat_end\ndata: {json.dumps({'message_id': message_id})}\n\n"

    async def get_history(
        self, db: aiosqlite.Connection, report_id: str
    ) -> ChatHistoryOut:
        # Validate report exists
        report = await report_model.get_report_by_id(db, report_id)
        if not report:
            raise ReportNotFoundError()

        history = await chat_model.get_chat_history(db, report_id)
        return ChatHistoryOut(
            report_id=report_id,
            messages=[
                ChatMessageOut(
                    id=msg["id"],
                    role=msg["role"],
                    content=msg["content"],
                    created_at=msg["created_at"],
                )
                for msg in history
            ],
        )
