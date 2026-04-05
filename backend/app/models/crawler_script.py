import aiosqlite


async def get_script(db: aiosqlite.Connection, company_id: str) -> dict | None:
    async with db.execute(
        "SELECT * FROM crawler_scripts WHERE company_id = ?", (company_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def upsert_script(db: aiosqlite.Connection, company_id: str, code: str) -> dict:
    await db.execute(
        """INSERT INTO crawler_scripts (company_id, code)
           VALUES (?, ?)
           ON CONFLICT(company_id) DO UPDATE SET code = ?, updated_at = datetime('now')""",
        (company_id, code, code),
    )
    await db.commit()
    return (await get_script(db, company_id))  # type: ignore


async def delete_script(db: aiosqlite.Connection, company_id: str) -> bool:
    cursor = await db.execute(
        "DELETE FROM crawler_scripts WHERE company_id = ?", (company_id,)
    )
    await db.commit()
    return cursor.rowcount > 0
