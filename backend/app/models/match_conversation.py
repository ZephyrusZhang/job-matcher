"""Data access for conversational job matching.

SQLite is the authority for anything the user sees: the conversation list and
the rendered messages, including each turn's tool timeline and cited jobs. The
agent's own working state (tool-call structure) lives in the Postgres LangGraph
checkpointer under the same id, so history still renders when the agent store is
unavailable.
"""

import json
import uuid
from typing import Any

import aiosqlite

# Long enough to be recognisable in the sidebar, short enough not to wrap.
TITLE_MAX_CHARS = 40


def _loads(value: str | None, fallback: Any) -> Any:
    """Decode a JSON column, tolerating nulls and corrupt payloads."""
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _dumps(value: Any) -> str | None:
    """Encode a JSON column, storing NULL for empty values."""
    if value in (None, [], {}):
        return None
    return json.dumps(value, ensure_ascii=False)


def _message_to_dict(row: aiosqlite.Row) -> dict:
    """Decode a message row."""
    data = dict(row)
    data["scope"] = _loads(data.get("scope"), None)
    data["tool_events"] = _loads(data.get("tool_events"), [])
    data["job_ids"] = _loads(data.get("job_ids"), [])
    return data


def derive_title(text: str) -> str:
    """Build a sidebar title from the first user message."""
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return "新对话"
    if len(cleaned) <= TITLE_MAX_CHARS:
        return cleaned
    return cleaned[:TITLE_MAX_CHARS] + "…"


# ── Conversations ─────────────────────────────────────────────────────────


async def create_conversation(db: aiosqlite.Connection, title: str = "") -> dict:
    """Create an empty conversation."""
    session_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO match_conversations (id, title) VALUES (?, ?)",
        (session_id, title or "新对话"),
    )
    await db.commit()
    return await get_conversation(db, session_id)  # type: ignore[return-value]


async def get_conversation(db: aiosqlite.Connection, session_id: str) -> dict | None:
    """Return one conversation."""
    async with db.execute(
        "SELECT * FROM match_conversations WHERE id = ?", (session_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def list_conversations(db: aiosqlite.Connection) -> list[dict]:
    """Return all conversations, most recently used first.

    Flat and unpaged — the sidebar shows the full history without grouping.
    """
    async with db.execute(
        """
        SELECT c.*, COUNT(m.id) AS message_count
        FROM match_conversations c
        LEFT JOIN match_messages m ON m.session_id = c.id
        GROUP BY c.id
        ORDER BY c.updated_at DESC
        """
    ) as cursor:
        return [dict(row) for row in await cursor.fetchall()]


async def rename_conversation(db: aiosqlite.Connection, session_id: str, title: str) -> bool:
    """Rename a conversation. Returns ``False`` when it does not exist."""
    cursor = await db.execute(
        "UPDATE match_conversations SET title = ?, updated_at = datetime('now') WHERE id = ?",
        (title, session_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def touch_conversation(db: aiosqlite.Connection, session_id: str) -> None:
    """Bump ``updated_at`` so the conversation floats to the top of the list."""
    await db.execute(
        "UPDATE match_conversations SET updated_at = datetime('now') WHERE id = ?",
        (session_id,),
    )
    await db.commit()


async def delete_conversation(db: aiosqlite.Connection, session_id: str) -> bool:
    """Delete a conversation and its messages via cascade."""
    cursor = await db.execute("DELETE FROM match_conversations WHERE id = ?", (session_id,))
    await db.commit()
    return cursor.rowcount > 0


# ── Messages ──────────────────────────────────────────────────────────────


async def add_message(
    db: aiosqlite.Connection,
    session_id: str,
    role: str,
    content: str = "",
    final_answer: str | None = None,
    scope: dict | None = None,
    resume_id: str | None = None,
    tool_events: list | None = None,
    job_ids: list | None = None,
    message_id: str | None = None,
) -> dict:
    """Append a message.

    Args:
        db: Open connection.
        session_id: Owning conversation.
        role: ``user`` or ``assistant``.
        content: For assistants this is narration — the thinking text emitted
            between tool calls, not the deliverable.
        final_answer: The ``final_answer`` tool payload, rendered as the body.
        scope: Company/favourite selection frozen at send time.
        resume_id: Resume used for this turn.
        tool_events: The turn's tool timeline.
        job_ids: Jobs cited by this turn.
        message_id: Pre-allocated id, so streaming can announce it up front.

    Returns:
        The stored message.
    """
    new_id = message_id or str(uuid.uuid4())
    await db.execute(
        """
        INSERT INTO match_messages
            (id, session_id, role, content, final_answer, scope, resume_id,
             tool_events, job_ids)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id,
            session_id,
            role,
            content,
            final_answer,
            _dumps(scope),
            resume_id,
            _dumps(tool_events),
            _dumps(job_ids),
        ),
    )
    await db.execute(
        "UPDATE match_conversations SET updated_at = datetime('now') WHERE id = ?",
        (session_id,),
    )
    await db.commit()
    return await get_message(db, new_id)  # type: ignore[return-value]


async def get_message(db: aiosqlite.Connection, message_id: str) -> dict | None:
    """Return one message."""
    async with db.execute("SELECT * FROM match_messages WHERE id = ?", (message_id,)) as cursor:
        row = await cursor.fetchone()
        return _message_to_dict(row) if row else None


async def list_messages(db: aiosqlite.Connection, session_id: str) -> list[dict]:
    """Return a conversation's messages oldest first."""
    async with db.execute(
        "SELECT * FROM match_messages WHERE session_id = ? ORDER BY created_at, rowid",
        (session_id,),
    ) as cursor:
        return [_message_to_dict(row) for row in await cursor.fetchall()]


async def count_messages(db: aiosqlite.Connection, session_id: str) -> int:
    """Return how many messages a conversation holds."""
    async with db.execute(
        "SELECT COUNT(*) FROM match_messages WHERE session_id = ?", (session_id,)
    ) as cursor:
        return (await cursor.fetchone())[0]
