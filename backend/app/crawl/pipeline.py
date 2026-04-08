"""Crawl pipeline: runs AgentRunner, normalizes output, and stores into DB."""
import asyncio
import hashlib
import json
import logging
import threading
import uuid

import aiosqlite

from app.crawl.category import normalize_category, prebatch_classify

logger = logging.getLogger(__name__)


def compute_content_hash(title: str, responsibilities: str, requirements_must: list[str]) -> str:
    payload = f"{title}|{responsibilities}|{'|'.join(sorted(requirements_must))}"
    return hashlib.sha256(payload.encode()).hexdigest()


def normalize_job(
    raw_job: dict,
    company_id: str,
    generic_cache: dict | None = None,
) -> dict:
    """Normalize crawler output into the DB schema."""
    title = raw_job.get("title", "")
    responsibilities = raw_job.get("responsibilities", "")
    requirements_str = raw_job.get("requirements", "")

    # Parse requirements string into list
    requirements_must = []
    if requirements_str:
        for line in requirements_str.replace("；", "\n").replace(";", "\n").split("\n"):
            line = line.strip().lstrip("0123456789.、- ")
            if line:
                requirements_must.append(line)

    raw_category = raw_job.get("category", "")
    category = normalize_category(
        raw_category,
        title=title,
        responsibilities=responsibilities,
        generic_cache=generic_cache,
    )
    location = raw_job.get("location")
    job_type = raw_job.get("job_type")
    department = raw_job.get("department")
    department_product = raw_job.get("department_product")
    education = raw_job.get("education")
    experience = raw_job.get("experience")
    posted_date = raw_job.get("posted_date") or raw_job.get("post_date")
    source_url = raw_job.get("source_url", "")
    summary = raw_job.get("summary")

    # For XHS-style data with raw field
    if "raw" in raw_job and not job_type:
        job_type = "intern"

    # Normalize job_type
    if job_type and job_type not in ("fulltime", "intern", "parttime", "contract"):
        job_type = "intern"

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
        jobs_new += 1

    await db.commit()
    return jobs_found, jobs_new, jobs_updated


def run_crawler(
    career_url: str,
    cancel_event: threading.Event | None = None,
) -> tuple[list[dict], str | None]:
    """Run the AgentRunner synchronously. Call from a thread.

    Returns (jobs, crawler_code) — crawler_code is the generated script if available.
    """
    from .agent import AgentRunner
    from .handlers import ConsoleHandler, FileHandler
    from .tools import sandbox_mgr

    runner = AgentRunner(
        handlers=[
            ConsoleHandler(verbose=True),
            FileHandler(log_dir="logs"),
        ],
        cancel_event=cancel_event,
    )
    jobs = runner.run(f"爬取该招聘网站的所有岗位信息：{career_url}")

    # Try to extract the generated crawler code for caching
    crawler_code = None
    try:
        crawler_code = sandbox_mgr.read_file("/home/user/crawler.py")
    except Exception:
        pass

    return jobs if jobs else [], crawler_code


def run_cached_crawler(
    code: str,
    cancel_event: threading.Event | None = None,
) -> list[dict]:
    """Run cached crawler code directly in sandbox, skip the agent.

    Returns the list of crawled job dicts.
    """
    from .sandbox import SandboxManager

    if cancel_event and cancel_event.is_set():
        return []

    # Use a fresh sandbox to avoid stale container references
    sandbox = SandboxManager()
    sandbox.ensure_sandbox()
    sandbox.write_file("/home/user/crawler.py", code)
    result = sandbox.run_command("python /home/user/crawler.py", timeout=300)

    if result["exit_code"] != 0:
        stderr = result.get("stderr", "")
        raise RuntimeError(f"Cached crawler failed (exit {result['exit_code']}): {stderr[-500:]}")

    # Read output
    try:
        content = sandbox.read_file("/home/user/output.json")
        data = json.loads(content)
        if isinstance(data, dict) and "jobs" in data:
            return data["jobs"]
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        raise RuntimeError(f"Failed to read crawler output: {e}")
