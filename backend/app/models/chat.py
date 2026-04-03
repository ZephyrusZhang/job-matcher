import aiosqlite


async def insert_message(
    db: aiosqlite.Connection,
    message_id: str,
    report_id: str,
    role: str,
    content: str,
) -> None:
    await db.execute(
        """
        INSERT INTO chat_messages (id, report_id, role, content, created_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        """,
        (message_id, report_id, role, content),
    )
    await db.commit()


async def get_chat_history(
    db: aiosqlite.Connection, report_id: str
) -> list[dict]:
    async with db.execute(
        """
        SELECT id, role, content, created_at
        FROM chat_messages
        WHERE report_id = ?
        ORDER BY created_at ASC
        """,
        (report_id,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
