"""Incremental deduplication for crawled jobs."""

import hashlib
import uuid


def compute_content_hash(title: str, responsibilities: str, requirements: str) -> str:
    """Generate SHA-256 hash from core job content for dedup."""
    payload = f"{title}|{responsibilities}|{requirements}"
    return hashlib.sha256(payload.encode()).hexdigest()


async def upsert_jobs(db, jobs: list[dict], company_id: str) -> dict:
    """Insert new jobs, update changed jobs, skip duplicates.

    Returns: {"jobs_found": int, "jobs_new": int, "jobs_updated": int}
    """
    stats = {"jobs_found": len(jobs), "jobs_new": 0, "jobs_updated": 0}

    for job in jobs:
        content_hash = compute_content_hash(
            job["title"],
            job.get("responsibilities") or "",
            job.get("requirements") or "",
        )

        existing = await db.fetch_one(
            "SELECT id, location, job_type, department, department_product, "
            "education, experience, posted_date, summary "
            "FROM jobs WHERE company_id = ? AND content_hash = ?",
            (company_id, content_hash),
        )

        if existing is None:
            job_id = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO jobs "
                "(id, company_id, title, category, location, job_type, "
                "responsibilities, requirements, "
                "department, department_product, education, experience, "
                "posted_date, source_url, summary, content_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    company_id,
                    job["title"],
                    job["category"],
                    job.get("location"),
                    job.get("job_type"),
                    job.get("responsibilities"),
                    job.get("requirements"),
                    job.get("department"),
                    job.get("department_product"),
                    job.get("education"),
                    job.get("experience"),
                    job.get("posted_date"),
                    job["source_url"],
                    job.get("summary"),
                    content_hash,
                ),
            )
            stats["jobs_new"] += 1
        else:
            changed = (
                existing["location"] != job.get("location")
                or existing["job_type"] != job.get("job_type")
                or existing["department"] != job.get("department")
                or existing["department_product"] != job.get("department_product")
                or existing["education"] != job.get("education")
                or existing["experience"] != job.get("experience")
                or existing["posted_date"] != job.get("posted_date")
                or existing["summary"] != job.get("summary")
            )
            if changed:
                await db.execute(
                    "UPDATE jobs SET location=?, job_type=?, department=?, "
                    "department_product=?, education=?, experience=?, "
                    "posted_date=?, summary=?, updated_at=datetime('now') "
                    "WHERE id=?",
                    (
                        job.get("location"),
                        job.get("job_type"),
                        job.get("department"),
                        job.get("department_product"),
                        job.get("education"),
                        job.get("experience"),
                        job.get("posted_date"),
                        job.get("summary"),
                        existing["id"],
                    ),
                )
                stats["jobs_updated"] += 1

    return stats
