"""Import crawled job data from tmp/ JSON files into the database."""
import asyncio
import hashlib
import json
import sys
import uuid
from pathlib import Path

import aiosqlite

# Add backend to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import load_config
from app.database import init_database

# Mapping of JSON file names to company IDs
FILE_COMPANY_MAP = {
    "bytedance.json": "bytedance",
    "tencent.json": "tencent",
    "xhs.json": "xiaohongshu",
}


def compute_content_hash(title: str, responsibilities: str, requirements_must: list[str]) -> str:
    payload = f"{title}|{responsibilities}|{'|'.join(sorted(requirements_must))}"
    return hashlib.sha256(payload.encode()).hexdigest()


def normalize_job(raw_job: dict, company_id: str) -> dict:
    """Normalize different JSON formats into a unified schema."""
    title = raw_job.get("title", "")
    responsibilities = raw_job.get("responsibilities", "")
    requirements_str = raw_job.get("requirements", "")

    # Parse requirements string into must_have list
    requirements_must = []
    if requirements_str:
        # Split by common delimiters
        for line in requirements_str.replace("；", "\n").replace(";", "\n").split("\n"):
            line = line.strip().lstrip("0123456789.、- ")
            if line:
                requirements_must.append(line)

    # Handle XHS format differences
    category = raw_job.get("category", "其他")
    location = raw_job.get("location", None)
    job_type = raw_job.get("job_type", None)
    department = raw_job.get("department", None)
    department_product = raw_job.get("department_product", None)
    education = raw_job.get("education", None)
    experience = raw_job.get("experience", None)
    posted_date = raw_job.get("posted_date") or raw_job.get("post_date")
    source_url = raw_job.get("source_url", "")
    summary = raw_job.get("summary", None)

    # For XHS, try to extract extra info from raw field
    if "raw" in raw_job:
        raw = raw_job["raw"]
        if not job_type and raw.get("jobType"):
            job_type = "intern"  # XHS campus positions are all intern

    # Ensure job_type is normalized
    if job_type and job_type not in ("fulltime", "intern", "parttime", "contract"):
        job_type = "intern"  # Default for campus recruitment

    content_hash = compute_content_hash(title, responsibilities, requirements_must)

    return {
        "id": str(uuid.uuid4()),
        "company_id": company_id,
        "title": title,
        "category": category,
        "location": location,
        "job_type": job_type,
        "responsibilities": responsibilities,
        "requirements_must": requirements_must,
        "requirements_nice": [],
        "department": department,
        "department_product": department_product,
        "education": education,
        "experience": experience,
        "posted_date": posted_date,
        "source_url": source_url,
        "summary": summary,
        "content_hash": content_hash,
    }


async def import_file(db: aiosqlite.Connection, file_path: Path, company_id: str) -> tuple[int, int]:
    """Import jobs from a JSON file. Returns (total, inserted)."""
    with open(file_path) as f:
        data = json.load(f)

    jobs = data.get("jobs", [])
    inserted = 0

    for raw_job in jobs:
        job = normalize_job(raw_job, company_id)

        # Check if content_hash already exists
        async with db.execute(
            "SELECT 1 FROM jobs WHERE content_hash = ? AND company_id = ?",
            (job["content_hash"], company_id),
        ) as cursor:
            if await cursor.fetchone():
                continue

        await db.execute(
            """
            INSERT INTO jobs (id, company_id, title, category, location, job_type,
                             responsibilities, requirements_must, requirements_nice,
                             department, department_product, education, experience,
                             posted_date, source_url, summary, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job["id"], job["company_id"], job["title"], job["category"],
                job["location"], job["job_type"], job["responsibilities"],
                json.dumps(job["requirements_must"], ensure_ascii=False),
                json.dumps(job["requirements_nice"], ensure_ascii=False),
                job["department"], job["department_product"],
                job["education"], job["experience"],
                job["posted_date"], job["source_url"],
                job["summary"], job["content_hash"],
            ),
        )
        inserted += 1

    await db.commit()
    return len(jobs), inserted


async def main():
    config = load_config(str(backend_dir / "config"))
    if not Path(config.database.path).is_absolute():
        config.database.path = str(backend_dir / config.database.path)

    await init_database(config.database)

    tmp_dir = backend_dir.parent / "tmp"
    if not tmp_dir.exists():
        print(f"tmp/ directory not found at {tmp_dir}")
        return

    db = await aiosqlite.connect(config.database.path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")

    total_imported = 0
    for filename, company_id in FILE_COMPANY_MAP.items():
        file_path = tmp_dir / filename
        if not file_path.exists():
            print(f"  Skipping {filename}: file not found")
            continue

        total, inserted = await import_file(db, file_path, company_id)
        total_imported += inserted
        print(f"  {filename}: {total} jobs found, {inserted} new jobs imported")

    await db.close()
    print(f"\nTotal: {total_imported} jobs imported successfully")


if __name__ == "__main__":
    asyncio.run(main())
