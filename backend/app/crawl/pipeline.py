"""Core crawl pipeline: Browser → Agent → Extractor → LLM → Dedup.

Architecture:
  - Agent analyzes the first N listing pages to learn selectors
  - Once locked, subsequent pages use selectors directly (no agent call)
  - Parse runs in background while browser crawls next page (pipeline overlap)
"""

import asyncio
import logging

from app.config import AppConfig, CompanyConfig
from app.crawl.agent import ListingAnalyzer
from app.crawl.dedup import upsert_jobs
from app.crawl.selector_cache import LockedPattern, PagePattern, SelectorCache
from app.llm.prompts.parse_job import build_parse_job_messages

logger = logging.getLogger(__name__)

_FALLBACK_SELECTOR = "a[href*='position'], a[href*='job'], a[href*='detail'], a[href*='post']"


async def _parse_one_page(llm_client, text: str, company_name: str, idx: int) -> list[dict]:
    messages = build_parse_job_messages(text, company_name)
    try:
        parsed = await llm_client.structured_parse(messages)
        jobs = parsed.get("jobs", [])
        logger.info("Detail %d: parsed %d jobs", idx, len(jobs))
        return jobs
    except Exception:
        logger.warning("Failed to parse detail %d", idx)
        return []


async def _extract_and_parse(
    extractor, llm_client, detail_pages: list[tuple[str, str]], company_name: str, offset: int
) -> list[dict]:
    """Extract text from detail pages and parse all in parallel via LLM.

    detail_pages: list of (html, source_url) tuples from browser.
    """
    htmls = [html for html, _url in detail_pages]
    urls = [url for _html, url in detail_pages]

    texts = await extractor.extract(htmls)
    # Pair each text with its source URL
    paired = [(t, u) for t, u in zip(texts, urls) if len(t.strip()) > 50]
    logger.info("Extracted %d texts, %d non-empty", len(texts), len(paired))

    if not paired:
        return []

    tasks = [
        _parse_one_page(llm_client, text, company_name, offset + i)
        for i, (text, _url) in enumerate(paired)
    ]
    results = await asyncio.gather(*tasks)

    # Inject source_url from the browser into each parsed job
    all_jobs = []
    for page_jobs, (_, source_url) in zip(results, paired):
        for job in page_jobs:
            job["source_url"] = source_url
        all_jobs.extend(page_jobs)
    return all_jobs


async def crawl_company(
    company: CompanyConfig,
    browser,
    extractor,
    llm_client,
    db,
    crawl_config=None,
) -> dict:
    """Execute the agent-driven pipelined crawl for a single company.

    Flow per listing page:
      1. If cache locked → use locked selector
         Else → agent analyzes page → cache records pattern
      2. Collect detail HTMLs (by links or selector)
      3. Start background extract+parse task (pipeline overlap)
      4. Navigate to next page

    Returns: {"jobs_found": int, "jobs_new": int, "jobs_updated": int}
    """
    logger.info("Starting crawl for %s (%s)", company.name, company.career_url)

    # Setup
    lock_threshold = crawl_config.agent_lock_threshold if crawl_config else 2
    learning_pages = crawl_config.agent_learning_pages if crawl_config else 2

    cache = SelectorCache(lock_threshold=lock_threshold)
    analyzer = ListingAnalyzer(llm_client)

    # If company has a hint selector, force-lock immediately
    if company.job_card_selector:
        cache.force_lock(LockedPattern(
            job_card_selector=company.job_card_selector,
            card_strategy="auto",
            next_page_selector=None,
        ))
        logger.info("Using hint selector: %s", company.job_card_selector)

    page = await browser.open_page(company.career_url)
    all_jobs: list[dict] = []
    pending_parse: asyncio.Task | None = None
    detail_offset = 0
    pages_crawled = 0

    try:
        while True:
            pages_crawled += 1
            logger.info("Processing listing page %d", pages_crawled)

            await browser.scroll_to_bottom(page)

            # ── Decide how to collect detail pages ──
            # detail_pages: list of (html, url) tuples
            pattern: PagePattern | None = None
            detail_pages: list[tuple[str, str]] = []

            if cache.is_locked():
                locked = cache.get_locked()
                detail_pages = await browser.collect_details_by_selector(
                    page, locked.job_card_selector, locked.card_strategy
                )
                if not detail_pages and pages_crawled <= learning_pages:
                    logger.warning("Locked selector returned 0 results, unlocking")
                    cache.unlock()

            if not cache.is_locked() and not detail_pages:
                if pages_crawled <= learning_pages:
                    try:
                        ctx = await browser.get_page_context(page)
                        pattern = await analyzer.analyze_page(ctx.text, ctx.url, ctx.html_snippet)
                        cache.record(pattern)
                        logger.info(
                            "Agent: selector=%s strategy=%s links=%d confidence=%.2f",
                            pattern.job_card_selector, pattern.card_strategy,
                            len(pattern.job_links), pattern.confidence,
                        )

                        if pattern.job_links:
                            detail_pages = await browser.collect_details_by_links(
                                page, pattern.job_links
                            )
                        elif pattern.job_card_selector:
                            detail_pages = await browser.collect_details_by_selector(
                                page, pattern.job_card_selector, pattern.card_strategy
                            )
                    except Exception:
                        logger.warning("Agent analysis failed, trying fallback selector")

                if not detail_pages:
                    detail_pages = await browser.collect_details_by_selector(
                        page, _FALLBACK_SELECTOR, "auto"
                    )

            logger.info("Page %d: collected %d detail pages", pages_crawled, len(detail_pages))

            # ── Pipeline: start parse in background ──
            if pending_parse is not None:
                jobs = await pending_parse
                all_jobs.extend(jobs)

            if detail_pages:
                pending_parse = asyncio.create_task(
                    _extract_and_parse(
                        extractor, llm_client, detail_pages, company.name, detail_offset
                    )
                )
                detail_offset += len(detail_pages)
            else:
                pending_parse = None

            # ── Pagination ──
            if company.max_pages != -1 and pages_crawled >= company.max_pages:
                logger.info("Reached max_pages limit (%d)", company.max_pages)
                break

            # Clean up any leaked tabs before pagination
            await browser.close_other_tabs(page)
            await browser.scroll_to_bottom(page)

            # Determine pagination selectors
            next_btn = None
            page_num_sel = None
            if cache.is_locked():
                locked = cache.get_locked()
                next_btn = locked.next_button_selector
                page_num_sel = locked.page_number_selector
            elif pattern:
                next_btn = pattern.next_button_selector
                page_num_sel = pattern.page_number_selector

            if not await browser.go_next_page(
                page, pages_crawled,
                next_button_selector=next_btn,
                page_number_selector=page_num_sel,
            ):
                logger.info("No more pages after page %d", pages_crawled)
                break

            # Wait for job cards to render after pagination (SPA pages)
            if cache.is_locked() and cache.get_locked().job_card_selector:
                await browser.wait_for_selector(page, cache.get_locked().job_card_selector)
            elif pattern and pattern.job_card_selector:
                await browser.wait_for_selector(page, pattern.job_card_selector)

        # Collect last batch
        if pending_parse is not None:
            jobs = await pending_parse
            all_jobs.extend(jobs)

    finally:
        await browser.close_page(page)

    logger.info("LLM parsed %d total jobs for %s", len(all_jobs), company.name)

    if not all_jobs:
        return {"jobs_found": 0, "jobs_new": 0, "jobs_updated": 0}

    result = await upsert_jobs(db, all_jobs, company.id)
    logger.info(
        "Crawl complete for %s: found=%d, new=%d, updated=%d",
        company.name, result["jobs_found"], result["jobs_new"], result["jobs_updated"],
    )
    return result
