import aiosqlite


async def get_all_companies(db: aiosqlite.Connection) -> list[dict]:
    async with db.execute(
        "SELECT * FROM companies ORDER BY created_at"
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_company_by_id(db: aiosqlite.Connection, company_id: str) -> dict | None:
    async with db.execute(
        "SELECT * FROM companies WHERE id = ?", (company_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_company(
    db: aiosqlite.Connection,
    company_id: str,
    name: str,
    career_url: str,
    crawl_interval_hours: int = 12,
) -> dict:
    await db.execute(
        """INSERT INTO companies (id, name, career_url, crawl_interval_hours)
           VALUES (?, ?, ?, ?)""",
        (company_id, name, career_url, crawl_interval_hours),
    )
    await db.commit()
    return (await get_company_by_id(db, company_id))  # type: ignore


async def update_company(
    db: aiosqlite.Connection,
    company_id: str,
    name: str | None = None,
    career_url: str | None = None,
    crawl_interval_hours: int | None = None,
) -> dict | None:
    sets = []
    params: list = []
    if name is not None:
        sets.append("name = ?")
        params.append(name)
    if career_url is not None:
        sets.append("career_url = ?")
        params.append(career_url)
    if crawl_interval_hours is not None:
        sets.append("crawl_interval_hours = ?")
        params.append(crawl_interval_hours)
    if not sets:
        return await get_company_by_id(db, company_id)
    sets.append("updated_at = datetime('now')")
    params.append(company_id)
    await db.execute(
        f"UPDATE companies SET {', '.join(sets)} WHERE id = ?", params
    )
    await db.commit()
    return await get_company_by_id(db, company_id)


async def delete_company(db: aiosqlite.Connection, company_id: str) -> bool:
    cursor = await db.execute(
        "DELETE FROM companies WHERE id = ?", (company_id,)
    )
    await db.commit()
    return cursor.rowcount > 0


async def company_exists(db: aiosqlite.Connection, company_id: str) -> bool:
    async with db.execute(
        "SELECT 1 FROM companies WHERE id = ?", (company_id,)
    ) as cursor:
        return await cursor.fetchone() is not None
