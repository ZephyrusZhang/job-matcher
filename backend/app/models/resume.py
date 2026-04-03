import json

import aiosqlite


async def upsert_resume(
    db: aiosqlite.Connection,
    filename: str,
    file_path: str,
    parsed_data: dict,
) -> None:
    """Insert or replace the single resume record (id=1)."""
    await db.execute(
        """
        INSERT OR REPLACE INTO resume (id, filename, file_path, parsed_data, uploaded_at)
        VALUES (1, ?, ?, ?, datetime('now'))
        """,
        (filename, file_path, json.dumps(parsed_data, ensure_ascii=False)),
    )
    await db.commit()


async def get_resume(db: aiosqlite.Connection) -> dict | None:
    async with db.execute("SELECT * FROM resume WHERE id = 1") as cursor:
        row = await cursor.fetchone()
        if row:
            d = dict(row)
            d["parsed_data"] = json.loads(d["parsed_data"])
            return d
        return None


async def delete_resume(db: aiosqlite.Connection) -> None:
    await db.execute("DELETE FROM resume WHERE id = 1")
    await db.commit()
