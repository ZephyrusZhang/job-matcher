"""Import crawled job data from tmp/ JSON files into the database."""
import asyncio
import json
import sys
from pathlib import Path

import aiosqlite

# Add backend to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import load_config
from app.crawl.pipeline import normalize_job
from app.database import init_database

# Mapping of JSON file names to company IDs
FILE_COMPANY_MAP = {
    "kuaishou.json": "kuaishou",
}


async def import_file(db: aiosqlite.Connection, file_path: Path, company_id: str) -> tuple[int, int, int]:
    """Import jobs from a JSON file. Returns (total, inserted, skipped)."""
    with open(file_path) as f:
        data = json.load(f)

    raw_jobs = data if isinstance(data, list) else data.get("jobs", [])
    inserted = 0
    skipped = 0

    for raw_job in raw_jobs:
        job = normalize_job(raw_job, company_id)

        # Skip non-tech jobs
        if not job["category"]:
            raw_cat = raw_job.get("category", "")
            print(f"    Skipped (unmapped category): '{job['title']}', raw_category='{raw_cat}'")
            skipped += 1
            continue

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
    return len(raw_jobs), inserted, skipped


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

        total, inserted, skipped = await import_file(db, file_path, company_id)
        total_imported += inserted
        print(f"  {filename}: {total} jobs found, {inserted} inserted, {skipped} skipped (unmapped category)")

    await db.close()
    print(f"\nTotal: {total_imported} jobs imported successfully")


if __name__ == "__main__":
    asyncio.run(main())
