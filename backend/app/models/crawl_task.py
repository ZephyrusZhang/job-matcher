import aiosqlite


async def create_task(
    db: aiosqlite.Connection, task_id: str, company_id: str
) -> None:
    await db.execute(
        "INSERT INTO crawl_tasks (id, company_id) VALUES (?, ?)",
        (task_id, company_id),
    )
    await db.commit()


async def update_task_status(
    db: aiosqlite.Connection,
    task_id: str,
    status: str,
    jobs_found: int = 0,
    jobs_new: int = 0,
    jobs_updated: int = 0,
    error_message: str | None = None,
) -> None:
    if status == "running":
        await db.execute(
            "UPDATE crawl_tasks SET status = ?, started_at = datetime('now') WHERE id = ?",
            (status, task_id),
        )
    elif status in ("completed", "failed", "cancelled"):
        await db.execute(
            """UPDATE crawl_tasks SET status = ?, jobs_found = ?, jobs_new = ?,
               jobs_updated = ?, error_message = ?, completed_at = datetime('now')
               WHERE id = ?""",
            (status, jobs_found, jobs_new, jobs_updated, error_message, task_id),
        )
    await db.commit()


async def has_active_task(db: aiosqlite.Connection, company_id: str) -> bool:
    async with db.execute(
        "SELECT 1 FROM crawl_tasks WHERE company_id = ? AND status IN ('pending', 'running')",
        (company_id,),
    ) as cursor:
        return await cursor.fetchone() is not None


async def get_tasks(
    db: aiosqlite.Connection,
    company_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    conditions = []
    params: list = []
    if company_id:
        conditions.append("company_id = ?")
        params.append(company_id)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_sql = f"SELECT COUNT(*) FROM crawl_tasks {where}"
    async with db.execute(count_sql, params) as cursor:
        total = (await cursor.fetchone())[0]

    offset = (page - 1) * page_size
    query = f"""
        SELECT * FROM crawl_tasks {where}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([page_size, offset])

    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], total


async def get_task_by_id(db: aiosqlite.Connection, task_id: str) -> dict | None:
    async with db.execute(
        "SELECT * FROM crawl_tasks WHERE id = ?", (task_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None
