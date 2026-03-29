"""Playwright browser management for page rendering."""

import logging
from collections.abc import AsyncGenerator
from urllib.parse import urljoin

from playwright.async_api import async_playwright

from app.config import CrawlConfig

logger = logging.getLogger(__name__)


class BrowserManager:
    def __init__(self, config: CrawlConfig):
        self._config = config
        self._playwright = None
        self._browser = None

    async def init(self):
        """Start browser. Bypasses system proxy to avoid connection issues."""
        self._playwright = await async_playwright().start()
        launch_args = ["--no-proxy-server"]
        self._browser = await self._playwright.chromium.launch(
            headless=self._config.browser_headless,
            args=launch_args,
        )
        logger.info("Browser initialized (headless=%s)", self._config.browser_headless)

    async def _navigate(self, page, url: str):
        """Navigate and wait for page to be fully loaded."""
        await page.goto(url, timeout=self._config.page_load_timeout)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

    async def crawl_listing_pages(
        self, career_url: str, max_pages: int = -1
    ) -> AsyncGenerator[list[str], None]:
        """Iterate through listing pages, yield detail page HTMLs per listing page.

        Yields one list[str] per listing page — the HTML of each detail page
        found on that listing page. The consumer can start processing while
        the next listing page is being crawled.
        """
        page = await self._browser.new_page()
        pages_crawled = 0

        try:
            await self._navigate(page, career_url)

            while True:
                pages_crawled += 1
                logger.info("Processing listing page %d", pages_crawled)

                await self._scroll_to_bottom(page)

                detail_hrefs = await self._collect_detail_links(page)
                logger.info(
                    "Listing page %d: found %d detail links",
                    pages_crawled, len(detail_hrefs),
                )

                # Visit each detail page and collect HTML
                listing_url = page.url
                detail_htmls = []
                for href in detail_hrefs:
                    try:
                        await self._navigate(page, href)
                        detail_htmls.append(await page.content())
                    except Exception:
                        logger.warning("Failed to load detail page: %s", href)

                yield detail_htmls

                # Check page limit
                if max_pages != -1 and pages_crawled >= max_pages:
                    logger.info("Reached max_pages limit (%d)", max_pages)
                    break

                # Navigate back and go to next listing page
                await self._navigate(page, listing_url)

                if not await self._go_to_next_page(page, current_page=pages_crawled):
                    logger.info("No more pages after page %d", pages_crawled)
                    break

        finally:
            await page.close()

    # Keep the old interface for backward compatibility (tests, simple usage)
    async def render_and_collect(
        self, career_url: str, max_pages: int = -1
    ) -> list[str]:
        """Collect all detail page HTMLs across all listing pages."""
        all_htmls: list[str] = []
        async for page_htmls in self.crawl_listing_pages(career_url, max_pages):
            all_htmls.extend(page_htmls)
        return all_htmls

    async def _scroll_to_bottom(self, page):
        """Scroll down to trigger lazy loading."""
        for _ in range(self._config.max_scroll_attempts):
            prev_height = await page.evaluate("document.body.scrollHeight")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == prev_height:
                break

    async def _collect_detail_links(self, page) -> list[str]:
        """Extract and deduplicate detail page links from the current page."""
        listing_url = page.url.rstrip("/")
        listing_path = listing_url.split("?")[0]

        links = await page.query_selector_all(
            "a[href*='position'], a[href*='job'], a[href*='detail']"
        )
        hrefs = []
        seen = set()
        for link in links:
            href = await link.get_attribute("href")
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            absolute = urljoin(listing_url, href)
            abs_path = absolute.split("?")[0].rstrip("/")

            if abs_path == listing_path or len(abs_path) <= len(listing_path):
                continue

            if absolute not in seen:
                seen.add(absolute)
                hrefs.append(absolute)
        return hrefs

    async def _go_to_next_page(self, page, current_page: int) -> bool:
        """Click the next page number in the pagination component."""
        next_num = current_page + 1
        next_text = str(next_num)

        try:
            locator = page.get_by_text(next_text, exact=True)
            count = await locator.count()

            for i in range(count):
                el = locator.nth(i)
                tag = await el.evaluate("el => el.tagName.toLowerCase()")
                if tag not in ("a", "button", "li", "span"):
                    continue

                is_pagination = await el.evaluate(
                    """el => {
                        const parent = el.closest('ul, nav, [class*="page"], [class*="paginat"]');
                        return parent !== null;
                    }"""
                )
                if not is_pagination:
                    continue

                await el.click()
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                logger.info("Navigated to page %d", next_num)
                return True
        except Exception:
            pass

        logger.info("Could not find page %d link", next_num)
        return False

    async def close(self):
        """Clean up browser resources."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
