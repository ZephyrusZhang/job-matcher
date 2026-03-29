"""Crawl4AI content extraction from HTML pages."""

import logging

from crawl4ai import AsyncWebCrawler

logger = logging.getLogger(__name__)


class ContentExtractor:
    async def extract(self, html_pages: list[str]) -> list[str]:
        """Extract clean text content from HTML pages using Crawl4AI.

        Returns list of text blocks (one per page).
        """
        results = []
        async with AsyncWebCrawler() as crawler:
            for html in html_pages:
                try:
                    result = await crawler.arun(url="raw:" + html)
                    if result.markdown:
                        results.append(result.markdown)
                except Exception:
                    logger.warning("Failed to extract content from HTML page")

        return results
