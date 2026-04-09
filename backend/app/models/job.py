import json
from datetime import datetime, timezone

import aiosqlite


def _serialize_location(value) -> str:
    """Serialize a location value (list or string) into the JSON-array storage form."""
    if value is None:
        return "[]"
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        # Already serialized — keep as-is
        stripped = value.lstrip()
        if stripped.startswith("["):
            return value
        # Legacy raw string — wrap as single-element list (caller should have
        # normalized upstream, this is just a safety net).
        return json.dumps([value] if value else [], ensure_ascii=False)
    return "[]"


async def get_jobs(
    db: aiosqlite.Connection,
    company_id: str,
    category: str | None = None,
    location: str | None = None,
    job_type: str | None = None,
    posted_within: str | None = None,
    sort_by: str = "posted_date",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """Return (jobs, total_count) with filtering and pagination."""
    conditions = ["j.company_id = ?"]
    params: list = [company_id]

    if category:
        categories = [c.strip() for c in category.split(",")]
        placeholders = ",".join("?" * len(categories))
        conditions.append(f"j.category IN ({placeholders})")
        params.extend(categories)

    if location:
        # location is stored as a JSON array string like '["北京","上海"]'.
        # Match when the requested city appears as an element — we look for
        # the exact quoted form to avoid "北京" matching "北京市" substrings.
        conditions.append("j.location LIKE ?")
        params.append(f'%"{location}"%')

    if job_type:
        conditions.append("j.job_type = ?")
        params.append(job_type)

    if posted_within:
        cutoff_map = {"24h": 1, "7d": 7, "30d": 30}
        days = cutoff_map.get(posted_within)
        if days:
            conditions.append("j.posted_date >= date('now', ?)")
            params.append(f"-{days} days")

    where = " AND ".join(conditions)

    # Count
    count_sql = f"SELECT COUNT(*) FROM jobs j WHERE {where}"
    async with db.execute(count_sql, params) as cursor:
        row = await cursor.fetchone()
        total = row[0]

    # Sort
    allowed_sort = {"posted_date": "j.posted_date", "title": "j.title"}
    sort_col = allowed_sort.get(sort_by, "j.posted_date")
    order = "DESC" if sort_order == "desc" else "ASC"

    offset = (page - 1) * page_size
    query = f"""
        SELECT j.*,
               CASE WHEN f.job_id IS NOT NULL THEN 1 ELSE 0 END AS is_favorited
        FROM jobs j
        LEFT JOIN favorites f ON j.id = f.job_id
        WHERE {where}
        ORDER BY {sort_col} {order}, j.created_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([page_size, offset])

    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
        jobs = [dict(row) for row in rows]

    return jobs, total


async def get_job_by_id(db: aiosqlite.Connection, job_id: str) -> dict | None:
    query = """
        SELECT j.*,
               CASE WHEN f.job_id IS NOT NULL THEN 1 ELSE 0 END AS is_favorited
        FROM jobs j
        LEFT JOIN favorites f ON j.id = f.job_id
        WHERE j.id = ?
    """
    async with db.execute(query, (job_id,)) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def search_jobs(
    db: aiosqlite.Connection,
    q: str,
    company_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """Full-text search across multiple fields."""
    like_pattern = f"%{q}%"
    conditions = [
        "(j.title LIKE ? OR j.responsibilities LIKE ? OR j.requirements_must LIKE ? "
        "OR j.requirements_nice LIKE ? OR j.category LIKE ? OR j.department LIKE ?)"
    ]
    params: list = [like_pattern] * 6

    if company_id:
        conditions.append("j.company_id = ?")
        params.append(company_id)

    where = " AND ".join(conditions)

    count_sql = f"SELECT COUNT(*) FROM jobs j WHERE {where}"
    async with db.execute(count_sql, params) as cursor:
        total = (await cursor.fetchone())[0]

    offset = (page - 1) * page_size
    query = f"""
        SELECT j.*,
               CASE WHEN f.job_id IS NOT NULL THEN 1 ELSE 0 END AS is_favorited
        FROM jobs j
        LEFT JOIN favorites f ON j.id = f.job_id
        WHERE {where}
        ORDER BY j.created_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([page_size, offset])

    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
        jobs = [dict(row) for row in rows]

    return jobs, total


async def suggest_jobs(
    db: aiosqlite.Connection,
    q: str,
    limit: int = 5,
) -> list[str]:
    """Return keyword suggestions based on job titles and skills."""
    like_pattern = f"%{q}%"
    # Collect matching titles
    query = """
        SELECT DISTINCT title FROM jobs
        WHERE title LIKE ?
        LIMIT ?
    """
    async with db.execute(query, (like_pattern, limit)) as cursor:
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def insert_job(db: aiosqlite.Connection, job: dict) -> None:
    """Insert a single job record."""
    await db.execute(
        """
        INSERT INTO jobs (id, company_id, title, category, location, job_type,
                         responsibilities, requirements_must, requirements_nice,
                         department, department_product, education, experience,
                         posted_date, source_url, summary, content_hash, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job["id"], job["company_id"], job["title"], job["category"],
            _serialize_location(job.get("location")), job.get("job_type"),
            job.get("responsibilities"),
            json.dumps(job.get("requirements_must", []), ensure_ascii=False),
            json.dumps(job.get("requirements_nice", []), ensure_ascii=False),
            job.get("department"), job.get("department_product"),
            job.get("education"), job.get("experience"),
            job.get("posted_date"), job["source_url"],
            job.get("summary"), job["content_hash"],
            job.get("created_at", datetime.now(timezone.utc).isoformat()),
            job.get("updated_at", datetime.now(timezone.utc).isoformat()),
        ),
    )


async def get_company_location_rows(
    db: aiosqlite.Connection, company_id: str
) -> list[dict]:
    """Return raw {location} rows for a company so the service can aggregate cities."""
    async with db.execute(
        "SELECT DISTINCT location FROM jobs WHERE company_id = ? AND location IS NOT NULL",
        (company_id,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_job_count_by_company(db: aiosqlite.Connection, company_id: str) -> int:
    async with db.execute(
        "SELECT COUNT(*) FROM jobs WHERE company_id = ?", (company_id,)
    ) as cursor:
        return (await cursor.fetchone())[0]


async def get_last_crawled_at(db: aiosqlite.Connection, company_id: str) -> str | None:
    async with db.execute(
        """SELECT completed_at FROM crawl_tasks
           WHERE company_id = ? AND status = 'completed'
           ORDER BY completed_at DESC LIMIT 1""",
        (company_id,),
    ) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else None
