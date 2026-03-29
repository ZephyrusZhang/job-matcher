"""Core crawl pipeline: Browser → Extractor → LLM → Dedup.

Uses a pipelined architecture: while Playwright crawls listing page N+1,
the LLM is concurrently parsing detail pages from listing page N.
"""

import asyncio
import logging

from app.config import CompanyConfig
from app.crawl.dedup import upsert_jobs
from app.llm.prompts.parse_job import build_parse_job_messages

logger = logging.getLogger(__name__)

_JOB_KEYWORDS = ("职位描述", "职位要求", "任职要求", "岗位职责")


def _is_job_detail(text: str) -> bool:
    return any(kw in text for kw in _JOB_KEYWORDS)


async def _parse_one_page(
    llm_client, text: str, company_name: str, index: int
) -> list[dict]:
    """Parse a single detail page, returning the list of jobs found."""
    messages = build_parse_job_messages(text, company_name)
    try:
        parsed = await llm_client.structured_parse(messages)
        jobs = parsed.get("jobs", [])
        logger.info("Detail %d: parsed %d jobs", index, len(jobs))
        return jobs
    except Exception:
        logger.warning("Failed to parse detail %d", index)
        return []


async def _extract_and_parse(
    extractor, llm_client, htmls: list[str], company_name: str, offset: int
) -> list[dict]:
    """Extract text from HTMLs, filter to job details, parse all in parallel."""
    texts = await extractor.extract(htmls)
    detail_texts = [t for t in texts if _is_job_detail(t)]
    logger.info(
        "Extracted %d texts, %d are job details", len(texts), len(detail_texts)
    )

    if not detail_texts:
        return []

    tasks = [
        _parse_one_page(llm_client, text, company_name, offset + i)
        for i, text in enumerate(detail_texts)
    ]
    results = await asyncio.gather(*tasks)
    return [job for page_jobs in results for job in page_jobs]


async def crawl_company(
    company: CompanyConfig,
    browser,
    extractor,
    llm_client,
    db,
) -> dict:
    """Execute the pipelined crawl for a single company.

    Pipeline stages run concurrently:
      - Stage A: Playwright crawls listing page N+1 (IO-bound: network)
      - Stage B: Extractor + LLM parses detail pages from page N (IO-bound: API)

    Returns: {"jobs_found": int, "jobs_new": int, "jobs_updated": int}
    """
    logger.info("Starting crawl for %s (%s)", company.name, company.career_url)

    all_jobs: list[dict] = []
    pending_parse: asyncio.Task | None = None
    detail_offset = 0

    async for page_htmls in browser.crawl_listing_pages(
        company.career_url, max_pages=company.max_pages
    ):
        # If there's a parse task from the previous listing page, let it
        # continue running — we'll collect its result later.
        # Meanwhile, kick off extract+parse for the current batch.

        # Wait for the previous batch to finish first, collect results
        if pending_parse is not None:
            jobs = await pending_parse
            all_jobs.extend(jobs)

        # Start extract+parse for this batch in the background
        pending_parse = asyncio.create_task(
            _extract_and_parse(
                extractor, llm_client, page_htmls, company.name, detail_offset
            )
        )
        detail_offset += len(page_htmls)

    # Collect the last batch
    if pending_parse is not None:
        jobs = await pending_parse
        all_jobs.extend(jobs)

    logger.info("LLM parsed %d total jobs for %s", len(all_jobs), company.name)

    if not all_jobs:
        return {"jobs_found": 0, "jobs_new": 0, "jobs_updated": 0}

    result = await upsert_jobs(db, all_jobs, company.id)
    logger.info(
        "Crawl complete for %s: found=%d, new=%d, updated=%d",
        company.name,
        result["jobs_found"],
        result["jobs_new"],
        result["jobs_updated"],
    )

    return result
