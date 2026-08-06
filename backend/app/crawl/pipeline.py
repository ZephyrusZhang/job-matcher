"""Crawl pipeline: normalizes crawler output and stores it into the database.

Running the agent itself lives in ``app/agents/crawler.py``; this module owns
normalization, deduplication and the cached-script fast path.
"""
import asyncio
import hashlib
import json
import logging
import threading
import uuid

import aiosqlite

from app.crawl.category import normalize_category, prebatch_classify
from app.crawl.job_type import normalize_job_type
from app.crawl.location import normalize_location

logger = logging.getLogger(__name__)


def compute_content_hash(title: str, description: str, requirements: str) -> str:
    payload = f"{title}|{description}|{requirements}"
    return hashlib.sha256(payload.encode()).hexdigest()


def normalize_job(
    raw_job: dict,
    company_id: str,
    generic_cache: dict | None = None,
) -> dict:
    """Normalize crawler output into the DB schema.

    ``description`` also accepts the old ``responsibilities`` key: crawler
    scripts generated before the schema change are cached in ``crawler_scripts``
    and still run unmodified whenever a crawl is triggered in ``cached`` mode.
    """
    title = raw_job.get("title", "")
    description = raw_job.get("description") or raw_job.get("responsibilities") or ""
    requirements = raw_job.get("requirements") or ""

    # A pre-migration script may still emit the old JSON-array shape.
    if isinstance(requirements, list):
        requirements = "\n".join(str(item) for item in requirements if item)

    raw_category = raw_job.get("category", "")
    category = normalize_category(
        raw_category,
        description=description,
        title=title,
        generic_cache=generic_cache,
    )
    location = normalize_location(raw_job.get("location"))
    raw_job_type = raw_job.get("job_type")
    posted_date = raw_job.get("posted_date") or raw_job.get("post_date")
    source_url = raw_job.get("source_url", "")

    # For XHS-style data with raw field: assume 实习 when nothing else is set
    if "raw" in raw_job and not raw_job_type:
        raw_job_type = "实习"

    # Normalize job_type → one of ["实习", "全职"]
    job_type = normalize_job_type(raw_job_type, title=title, description=description)

    content_hash = compute_content_hash(title, description, requirements)

    return {
        "id": str(uuid.uuid4()),
        "company_id": company_id,
        "title": title,
        "category": category,
        "location": location,
        "job_type": job_type,
        "description": description,
        "requirements": requirements,
        "posted_date": posted_date,
        "source_url": source_url,
        "content_hash": content_hash,
    }


async def store_jobs(
    db: aiosqlite.Connection,
    raw_jobs: list[dict],
    company_id: str,
    cancel_event: threading.Event | None = None,
) -> tuple[int, int, int]:
    """Normalize and store crawled jobs. Returns (jobs_found, jobs_new, jobs_updated).

    If cancel_event is set, finishes the current insert then stops.
    """
    jobs_found = len(raw_jobs)
    jobs_new = 0
    jobs_updated = 0

    # Pre-batch LLM classification (32 jobs per request)
    logger.info(f"store_jobs: prebatch classifying {jobs_found} jobs...")
    generic_cache = await asyncio.get_event_loop().run_in_executor(
        None, prebatch_classify, raw_jobs, 32
    )
    logger.info(f"store_jobs: prebatch done, generic_cache={len(generic_cache)} entries")

    for raw_job in raw_jobs:
        # Check cancellation before processing next job
        if cancel_event and cancel_event.is_set():
            logger.info(f"store_jobs cancelled after {jobs_new} new inserts")
            break

        job = normalize_job(raw_job, company_id, generic_cache=generic_cache)

        # category is None only when LLM explicitly classified as non-tech
        if not job["category"]:
            continue

        # Dedup by source_url: same company + same page = same job
        async with db.execute(
            "SELECT id FROM jobs WHERE source_url = ? AND company_id = ?",
            (job["source_url"], company_id),
        ) as cursor:
            if await cursor.fetchone():
                continue

        # Insert completes fully before next iteration checks cancel
        await db.execute(
            """
            INSERT INTO jobs (id, company_id, title, category, location, job_type,
                             description, requirements, posted_date, source_url,
                             content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job["id"], job["company_id"], job["title"], job["category"],
                json.dumps(job["location"], ensure_ascii=False),
                job["job_type"], job["description"], job["requirements"],
                job["posted_date"], job["source_url"], job["content_hash"],
            ),
        )
        jobs_new += 1

    await db.commit()
    return jobs_found, jobs_new, jobs_updated


def run_cached_crawler(
    code: str,
    cancel_event: threading.Event | None = None,
    company_id: str | None = None,
    task_id: str | None = None,
) -> list[dict]:
    """Run cached crawler code directly in sandbox, skip the agent.

    Args:
        code: The stored crawler script.
        cancel_event: Checked before starting.
        company_id: Names/labels the container, e.g. ``jm-cached-bilibili-7719674d``.
        task_id: Crawl task ID, used for the name suffix and the task label.

    Returns:
        The list of crawled job dicts.
    """
    from .sandbox import (
        LABEL_COMPANY,
        LABEL_MODE,
        LABEL_TASK,
        SandboxManager,
        build_sandbox_name,
    )

    if cancel_event and cancel_event.is_set():
        return []

    # A fresh sandbox avoids stale container references; the context manager
    # removes it on the way out, keeping it only when the run raised and
    # KEEP_SANDBOX_ON_FAILURE is set.
    with SandboxManager(
        name=build_sandbox_name("cached", company_id, task_id),
        labels={
            LABEL_MODE: "cached",
            LABEL_COMPANY: company_id or "",
            LABEL_TASK: task_id or "",
        },
    ) as sandbox:
        sandbox.ensure_sandbox()
        sandbox.write_file("/home/user/crawler.py", code)
        result = sandbox.run_command("python /home/user/crawler.py", timeout=300)

        if result["exit_code"] != 0:
            stderr = result.get("stderr", "")
            raise RuntimeError(f"Cached crawler failed (exit {result['exit_code']}): {stderr[-500:]}")

        try:
            content = sandbox.read_file("/home/user/output.json")
            data = json.loads(content)
        except Exception as e:
            raise RuntimeError(f"Failed to read crawler output: {e}")

    if isinstance(data, dict) and "jobs" in data:
        return data["jobs"]
    if isinstance(data, list):
        return data
    return []
