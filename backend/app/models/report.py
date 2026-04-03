import json

import aiosqlite


async def upsert_report(
    db: aiosqlite.Connection,
    report_id: str,
    company_id: str,
    report_type: str,
    content: str,
    job_ids: list[str],
    preferences: dict,
) -> None:
    """Insert or replace a report (unique on company_id + report_type)."""
    await db.execute(
        """
        INSERT OR REPLACE INTO reports (id, company_id, report_type, content, job_ids, preferences, created_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            report_id,
            company_id,
            report_type,
            content,
            json.dumps(job_ids, ensure_ascii=False),
            json.dumps(preferences, ensure_ascii=False),
        ),
    )
    await db.commit()


async def get_report(
    db: aiosqlite.Connection, company_id: str, report_type: str
) -> dict | None:
    async with db.execute(
        "SELECT * FROM reports WHERE company_id = ? AND report_type = ?",
        (company_id, report_type),
    ) as cursor:
        row = await cursor.fetchone()
        if row:
            d = dict(row)
            d["job_ids"] = json.loads(d["job_ids"])
            d["preferences"] = json.loads(d["preferences"])
            return d
        return None


async def get_report_by_id(db: aiosqlite.Connection, report_id: str) -> dict | None:
    async with db.execute(
        "SELECT * FROM reports WHERE id = ?", (report_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if row:
            d = dict(row)
            d["job_ids"] = json.loads(d["job_ids"])
            d["preferences"] = json.loads(d["preferences"])
            return d
        return None


async def delete_report(
    db: aiosqlite.Connection, company_id: str, report_type: str
) -> int:
    """Delete report and return number deleted. Chat messages cascade."""
    cursor = await db.execute(
        "DELETE FROM reports WHERE company_id = ? AND report_type = ?",
        (company_id, report_type),
    )
    await db.commit()
    return cursor.rowcount


async def delete_all_reports(db: aiosqlite.Connection) -> tuple[int, int]:
    """Delete all reports, return (reports_deleted, messages_deleted)."""
    async with db.execute("SELECT COUNT(*) FROM chat_messages") as cursor:
        messages_count = (await cursor.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM reports") as cursor:
        reports_count = (await cursor.fetchone())[0]
    await db.execute("DELETE FROM reports")
    await db.commit()
    return reports_count, messages_count
