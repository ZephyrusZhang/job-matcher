"""Conversational job matching: conversation CRUD, turn submission, streaming.

Submitting a turn and watching it are deliberately separate requests. A submit
carries the question, so it can never be safely retried; a subscription carries
nothing but the conversation id, so it can be reopened any number of times.
Splitting them removes the whole question of "which stream is replayable" —
every stream is.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator

import aiosqlite
from langchain_core.messages import AIMessage, ToolMessage

from app.agents.match_tools import TurnContext, reset_turn_context, set_turn_context
from app.agents.matcher import matcher_agent
from app.core.langgraph.base import AgentCancelled
from app.core.logging import logger
from app.database import get_db
from app.exceptions import AppError
from app.models import job as job_model
from app.models import match_conversation as conv_model
from app.models import resume as resume_model
from app.schemas.agent import Message
from app.schemas.match import (
    ConversationOut,
    MatchMessageOut,
    MatchScope,
    SendMessageRequest,
)
from app.services.match_runs import HEARTBEAT_SECONDS, Run, registry
from app.utils.job_citations import extract_job_ids

# Guards against a wedged agent holding a run open forever.
TURN_TIMEOUT_SECONDS = 300

# How long `stop` waits for the agent to reach a node boundary and unwind.
STOP_TIMEOUT_SECONDS = 10


class ConversationNotFoundError(AppError):
    """Raised when a conversation id does not exist."""

    def __init__(self):
        """Build the 404."""
        super().__init__("CONVERSATION_NOT_FOUND", "对话不存在", 404)


class SessionBusyError(AppError):
    """Raised when a conversation already has a turn in flight."""

    def __init__(self):
        """Build the 409."""
        super().__init__("SESSION_BUSY", "当前对话正在生成中，请先等待或停止", 409)


def _sse(event: str, data: dict, seq: int | None = None) -> str:
    """Format one server-sent event, carrying its sequence number as the id."""
    head = f"id: {seq}\n" if seq is not None else ""
    return f"{head}event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class MatchService:
    """Owns conversations and drives the match agent for each turn."""

    def __init__(self, db_path: str):
        """Store the SQLite path runs and agent tools open connections against."""
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
        run = registry.get(session_id)
        if run is not None:
            await self.stop(db, session_id)

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

        Rows are read straight from SQLite: a running turn persists every frame
        before publishing it, so the row is never behind what a client saw. The
        registry is consulted only to tell a genuinely live turn apart from one
        stranded by a backend restart.

        Raises:
            ConversationNotFoundError: When the conversation does not exist.
        """
        if not await conv_model.get_conversation(db, session_id):
            raise ConversationNotFoundError()

        if registry.get(session_id) is None:
            await conv_model.mark_stale_running(db, session_id)

        return [MatchMessageOut(**row) for row in await conv_model.list_messages(db, session_id)]

    # ── Submitting a turn ─────────────────────────────────────────────────

    async def submit(
        self,
        db: aiosqlite.Connection,
        session_id: str,
        request: SendMessageRequest,
    ) -> str:
        """Record a user turn and start the agent, returning the message id.

        Returns as soon as the run is scheduled; the answer is watched through
        ``subscribe``. The run's lifetime is owned by the registry, not by any
        HTTP request, so a client that disconnects does not abandon the turn.

        Raises:
            ConversationNotFoundError: When the conversation does not exist.
            SessionBusyError: When a turn is already in flight.
        """
        conversation = await conv_model.get_conversation(db, session_id)
        if not conversation:
            raise ConversationNotFoundError()
        if registry.get(session_id) is not None:
            raise SessionBusyError()

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
        await conv_model.add_message(
            db,
            session_id,
            role="assistant",
            message_id=message_id,
            scope=request.scope.model_dump(),
            resume_id=resume_id,
            status="running",
        )

        # The run holds its own connection for the whole turn: the per-request
        # one is closed the moment this handler returns.
        run_db = await get_db(self.db_path)
        run = Run(session_id, message_id, run_db)
        registry.add(run)
        run.task = asyncio.create_task(
            self._drive(run, request, resume["label"] if resume else None, resume_id)
        )
        return message_id

    async def _drive(
        self,
        run: Run,
        request: SendMessageRequest,
        resume_label: str | None,
        resume_id: str | None,
    ) -> None:
        """Run one agent turn to completion and close the run out."""
        from app.services.match_stream import MatchStreamBridge

        bridge = MatchStreamBridge(run)
        turn_ctx = TurnContext(
            scope=request.scope,
            resume_id=resume_id,
            resume_label=resume_label,
            db_path=self.db_path,
        )
        token = set_turn_context(turn_ctx)
        status = "completed"

        try:
            await asyncio.wait_for(
                matcher_agent.run(
                    [Message(role="user", content=request.content)],
                    run.session_id,
                    callbacks=[bridge],
                    cancel_check=run.cancel.is_set,
                ),
                timeout=TURN_TIMEOUT_SECONDS,
            )
        except AgentCancelled:
            status = "stopped"
            logger.info("match_turn_stopped", session_id=run.session_id)
        except asyncio.CancelledError:
            status = "stopped"
            raise
        except Exception as e:
            status = "failed"
            logger.exception("match_turn_failed", session_id=run.session_id, error=str(e))
            await run.emit("error", {"code": "AGENT_FAILED", "message": str(e)[:300]})
        finally:
            reset_turn_context(token)
            await self._close_out(run, status)

    async def _close_out(self, run: Run, status: str) -> None:
        """Resolve citations, write the terminal row, and retire the run."""
        try:
            # The model is instructed to finish via final_answer; if it answered
            # in plain text instead, the *trailing* narration is that answer.
            # Only that one — the short interstitial lines between tool calls
            # belong to the trace, and gluing them onto the front of the answer
            # is what used to make a reply open with "好的，我先看看…".
            if (
                not run.final_answer
                and run.steps
                and run.steps[-1]["type"] == "narration"
            ):
                run.final_answer = run.steps.pop()["content"]

            job_ids = await self._resolve_citations(run.db, run.final_answer)
            await run.finish(status, job_ids)
        except Exception as e:
            logger.exception("match_close_out_failed", session_id=run.session_id, error=str(e))
        finally:
            registry.discard(run.session_id)
            await run.db.close()

    async def _resolve_citations(self, db: aiosqlite.Connection, final_answer: str) -> list[str]:
        """Turn the answer's ``:job[...]`` markers into a stored job list.

        The markers are what the turn actually recommended, unlike everything
        the agent merely looked at (one ``search_jobs`` call alone can return
        40 rows).
        """
        cited = extract_job_ids(final_answer)
        if not cited:
            return []

        job_ids = await job_model.filter_existing(db, cited)
        if len(job_ids) != len(cited):
            logger.warning(
                "match_citation_unknown",
                job_ids=[j for j in cited if j not in job_ids],
            )
        return job_ids

    # ── Watching a turn ───────────────────────────────────────────────────

    async def subscribe(
        self, db: aiosqlite.Connection, session_id: str
    ) -> AsyncGenerator[str, None]:
        """Stream a turn, starting from a snapshot of wherever it currently is.

        The first frame is always a complete snapshot rather than a delta, so a
        client can reconnect after any gap without asking for a replay — and,
        because the snapshot and the subscription are taken under one lock, the
        snapshot's ``seq`` and the first live frame are necessarily adjacent.

        Raises:
            ConversationNotFoundError: When the conversation does not exist.
        """
        if not await conv_model.get_conversation(db, session_id):
            raise ConversationNotFoundError()

        run = registry.get(session_id)
        if run is None:
            # Nothing in flight: hand back the stored terminal state so the
            # client can settle its UI without a second request.
            await conv_model.mark_stale_running(db, session_id)
            rows = await conv_model.list_messages(db, session_id)
            last = rows[-1] if rows and rows[-1]["role"] == "assistant" else None
            yield _sse(
                "snapshot",
                {
                    "message_id": last["id"] if last else None,
                    "seq": last["seq"] if last else 0,
                    "status": last["status"] if last else "completed",
                    "steps": last["steps"] if last else [],
                    "final_answer": (last["final_answer"] if last else "") or "",
                    "job_ids": last["job_ids"] if last else [],
                },
            )
            return

        snapshot, queue = await run.attach()
        yield _sse("snapshot", snapshot, seq=snapshot["seq"])

        try:
            while True:
                try:
                    frame = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    # A comment frame keeps the connection observable, so a
                    # reader never blocks forever on a silently dead socket.
                    yield ": ping\n\n"
                    continue
                if frame is None:
                    break
                yield _sse(frame["event"], frame["data"], seq=frame["seq"])
        finally:
            run.detach(queue)

    # ── Stopping a turn ───────────────────────────────────────────────────

    async def stop(self, db: aiosqlite.Connection, session_id: str) -> None:
        """Cancel the in-flight turn, if any. Idempotent.

        Raises:
            ConversationNotFoundError: When the conversation does not exist.
        """
        if not await conv_model.get_conversation(db, session_id):
            raise ConversationNotFoundError()

        run = registry.get(session_id)
        if run is None:
            return

        run.cancel.set()
        try:
            await asyncio.wait_for(run.finished.wait(), timeout=STOP_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            logger.warning("match_stop_timeout", session_id=session_id)
            if run.task and not run.task.done():
                run.task.cancel()

        await self._repair_checkpoint(session_id)

    async def _repair_checkpoint(self, session_id: str) -> None:
        """Answer any tool calls the cancelled turn left dangling.

        ``cancel_check`` is polled at the top of the tool node, so a turn can be
        cut between an ``AIMessage`` carrying ``tool_calls`` and the
        ``ToolMessage`` replies to them. A tool call without a matching reply
        makes the *next* request on this thread fail, so the gap is filled with
        placeholders rather than left for the user to trip over.
        """
        try:
            graph = await matcher_agent._get_graph()
            config = {"configurable": {"thread_id": session_id}}
            state = await graph.aget_state(config)
            messages = (state.values or {}).get("messages") or []
            if not messages:
                return

            last = messages[-1]
            if not isinstance(last, AIMessage) or not last.tool_calls:
                return

            await graph.aupdate_state(
                config,
                {
                    "messages": [
                        ToolMessage(
                            content='{"error": "用户已停止本轮"}',
                            name=call["name"],
                            tool_call_id=call["id"],
                        )
                        for call in last.tool_calls
                    ]
                },
            )
            logger.info(
                "match_checkpoint_repaired",
                session_id=session_id,
                tool_calls=len(last.tool_calls),
            )
        except Exception as e:
            logger.warning("match_checkpoint_repair_failed", session_id=session_id, error=str(e))


def build_scope_from_dict(raw: dict | None) -> MatchScope:
    """Rebuild a scope from stored JSON, tolerating older/absent payloads."""
    if not raw:
        return MatchScope()
    try:
        return MatchScope(**raw)
    except Exception:
        return MatchScope()
