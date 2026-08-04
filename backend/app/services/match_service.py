"""Conversational job matching: conversation CRUD plus one streamed turn."""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator

import aiosqlite

from app.agents.match_tools import TurnContext, reset_turn_context, set_turn_context
from app.agents.matcher import matcher_agent
from app.core.logging import logger
from app.exceptions import AppError
from app.models import match_conversation as conv_model
from app.models import resume as resume_model
from app.schemas.agent import Message
from app.schemas.match import (
    ConversationOut,
    MatchMessageOut,
    MatchScope,
    SendMessageRequest,
)

# Guards against a wedged agent holding an SSE connection open forever.
TURN_TIMEOUT_SECONDS = 300


class ConversationNotFoundError(AppError):
    """Raised when a conversation id does not exist."""

    def __init__(self):
        """Build the 404."""
        super().__init__("CONVERSATION_NOT_FOUND", "对话不存在", 404)


def _sse(event: str, data: dict) -> str:
    """Format one server-sent event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class MatchService:
    """Owns conversations and drives the match agent for each turn."""

    def __init__(self, db_path: str):
        """Store the SQLite path the agent's tools open connections against."""
        self.db_path = db_path

    # ── Conversations ─────────────────────────────────────────────────────

    async def create_conversation(self, db: aiosqlite.Connection, title: str = "") -> ConversationOut:
        """Create an empty conversation."""
        row = await conv_model.create_conversation(db, title)
        return ConversationOut(**row, message_count=0)

    async def list_conversations(self, db: aiosqlite.Connection) -> list[ConversationOut]:
        """List conversations, most recently used first."""
        return [ConversationOut(**row) for row in await conv_model.list_conversations(db)]

    async def rename_conversation(
        self, db: aiosqlite.Connection, session_id: str, title: str
    ) -> ConversationOut:
        """Rename a conversation.

        Raises:
            ConversationNotFoundError: When it does not exist.
        """
        if not await conv_model.rename_conversation(db, session_id, title):
            raise ConversationNotFoundError()
        row = await conv_model.get_conversation(db, session_id)
        count = await conv_model.count_messages(db, session_id)
        return ConversationOut(**row, message_count=count)  # type: ignore[arg-type]

    async def delete_conversation(self, db: aiosqlite.Connection, session_id: str) -> None:
        """Delete a conversation, its messages, and its agent checkpoints.

        Raises:
            ConversationNotFoundError: When it does not exist.
        """
        if not await conv_model.delete_conversation(db, session_id):
            raise ConversationNotFoundError()

        # The conversation id doubles as the LangGraph thread id. A failure here
        # leaves orphaned checkpoints, which is harmless — don't fail the delete.
        try:
            await matcher_agent.clear_chat_history(session_id)
        except Exception as e:
            logger.warning("checkpoint_clear_failed", session_id=session_id, error=str(e))

    async def list_messages(
        self, db: aiosqlite.Connection, session_id: str
    ) -> list[MatchMessageOut]:
        """Return a conversation's messages.

        Raises:
            ConversationNotFoundError: When the conversation does not exist.
        """
        if not await conv_model.get_conversation(db, session_id):
            raise ConversationNotFoundError()
        return [MatchMessageOut(**row) for row in await conv_model.list_messages(db, session_id)]

    # ── One streamed turn ─────────────────────────────────────────────────

    async def stream_turn(
        self,
        db: aiosqlite.Connection,
        session_id: str,
        request: SendMessageRequest,
    ) -> AsyncGenerator[str, None]:
        """Run one agent turn, yielding SSE frames as it goes.

        Args:
            db: Open connection, used for persistence around the turn.
            session_id: Target conversation; also the LangGraph thread id.
            request: The user's message, scope, and chosen resume.

        Yields:
            SSE-formatted strings.

        Raises:
            ConversationNotFoundError: When the conversation does not exist.
        """
        conversation = await conv_model.get_conversation(db, session_id)
        if not conversation:
            raise ConversationNotFoundError()

        resume = await resume_model.get_resume(db, request.resume_id)
        resume_id = resume["id"] if resume else None

        await conv_model.add_message(
            db,
            session_id,
            role="user",
            content=request.content,
            scope=request.scope.model_dump(),
            resume_id=resume_id,
        )

        # Name the conversation after its opening question.
        if not conversation["title"] or conversation["title"] == "新对话":
            await conv_model.rename_conversation(
                db, session_id, conv_model.derive_title(request.content)
            )

        message_id = str(uuid.uuid4())
        yield _sse("message_start", {"message_id": message_id})

        queue: asyncio.Queue = asyncio.Queue()
        from app.services.match_stream import MatchStreamBridge

        bridge = MatchStreamBridge(queue)
        turn_ctx = TurnContext(
            scope=request.scope,
            resume_id=resume_id,
            resume_label=resume["label"] if resume else None,
            db_path=self.db_path,
        )

        token = set_turn_context(turn_ctx)
        try:
            agent_task = asyncio.create_task(self._run_agent(request, session_id, bridge))

            async for frame in self._drain(queue, agent_task):
                yield frame

            error = agent_task.exception() if agent_task.done() else None
            if error is not None:
                logger.exception("match_turn_failed", session_id=session_id, error=str(error))
                yield _sse("error", {"code": "AGENT_FAILED", "message": str(error)[:300]})
        finally:
            reset_turn_context(token)

        # The model is instructed to finish via final_answer; if it answered in
        # plain text instead, use that rather than showing the user nothing.
        final_answer = bridge.final_answer or bridge.narration
        narration = bridge.narration if bridge.final_answer else ""

        if turn_ctx.cited_job_ids:
            yield _sse("jobs", {"job_ids": turn_ctx.cited_job_ids})

        await conv_model.add_message(
            db,
            session_id,
            role="assistant",
            content=narration,
            final_answer=final_answer,
            scope=request.scope.model_dump(),
            resume_id=resume_id,
            tool_events=bridge.tool_events,
            job_ids=turn_ctx.cited_job_ids,
            message_id=message_id,
        )

        yield _sse("message_end", {"message_id": message_id})

    async def _run_agent(
        self, request: SendMessageRequest, session_id: str, bridge
    ) -> None:
        """Invoke the agent for one turn.

        Only the new user message is passed: LangGraph's ``add_messages``
        reducer appends it to the checkpointed history for this thread, so prior
        turns must not be re-sent.
        """
        await asyncio.wait_for(
            matcher_agent.run(
                [Message(role="user", content=request.content)],
                session_id,
                callbacks=[bridge],
            ),
            timeout=TURN_TIMEOUT_SECONDS,
        )

    async def _drain(self, queue: asyncio.Queue, agent_task: asyncio.Task) -> AsyncGenerator[str, None]:
        """Yield queued events until the agent finishes and the queue empties."""
        while True:
            if agent_task.done() and queue.empty():
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                continue
            yield _sse(item["event"], item["data"])

        # Surface a cancelled/failed task rather than hanging.
        if not agent_task.done():
            agent_task.cancel()


def build_scope_from_dict(raw: dict | None) -> MatchScope:
    """Rebuild a scope from stored JSON, tolerating older/absent payloads."""
    if not raw:
        return MatchScope()
    try:
        return MatchScope(**raw)
    except Exception:
        return MatchScope()
