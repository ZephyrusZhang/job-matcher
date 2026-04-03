import aiosqlite


async def add_favorite(db: aiosqlite.Connection, job_id: str) -> str:
    """Add a favorite, return created_at."""
    await db.execute(
        "INSERT OR IGNORE INTO favorites (job_id) VALUES (?)", (job_id,)
    )
    await db.commit()
    async with db.execute(
        "SELECT created_at FROM favorites WHERE job_id = ?", (job_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return row[0]


async def remove_favorite(db: aiosqlite.Connection, job_id: str) -> None:
    await db.execute("DELETE FROM favorites WHERE job_id = ?", (job_id,))
    await db.commit()


async def get_favorites(
    db: aiosqlite.Connection, company_id: str | None = None
) -> list[dict]:
    if company_id:
        query = """
            SELECT f.job_id, j.title, j.category, j.location, f.created_at,
                   j.company_id
            FROM favorites f
            JOIN jobs j ON f.job_id = j.id
            WHERE j.company_id = ?
            ORDER BY f.created_at DESC
        """
        params = (company_id,)
    else:
        query = """
            SELECT f.job_id, j.title, j.category, j.location, f.created_at,
                   j.company_id
            FROM favorites f
            JOIN jobs j ON f.job_id = j.id
            ORDER BY f.created_at DESC
        """
        params = ()

    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_favorites_summary(db: aiosqlite.Connection) -> list[dict]:
    query = """
        SELECT j.company_id, COUNT(*) as count
        FROM favorites f
        JOIN jobs j ON f.job_id = j.id
        GROUP BY j.company_id
    """
    async with db.execute(query) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_favorite_jobs_by_company(
    db: aiosqlite.Connection, company_id: str
) -> list[dict]:
    """Get full job details for favorites of a specific company."""
    query = """
        SELECT j.* FROM jobs j
        JOIN favorites f ON j.id = f.job_id
        WHERE j.company_id = ?
        ORDER BY f.created_at DESC
    """
    async with db.execute(query, (company_id,)) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def is_favorited(db: aiosqlite.Connection, job_id: str) -> bool:
    async with db.execute(
        "SELECT 1 FROM favorites WHERE job_id = ?", (job_id,)
    ) as cursor:
        return await cursor.fetchone() is not None
