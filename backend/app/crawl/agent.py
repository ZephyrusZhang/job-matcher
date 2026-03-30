"""LLM agent for analyzing listing page structure.

Examines page HTML to determine:
- CSS selector for job card elements
- Whether to use href or click strategy
- Pagination button selector
"""

import logging
import re
from html.parser import HTMLParser

from app.crawl.selector_cache import PagePattern
from app.llm.prompts.analyze_listing import build_analyze_listing_messages

logger = logging.getLogger(__name__)

# Tags and attributes to keep when simplifying HTML
_KEEP_ATTRS = {"class", "id", "href", "data-id", "data-href", "role", "aria-label"}
_REMOVE_TAGS = {"script", "style", "svg", "noscript", "link", "meta", "iframe"}
_TEXT_TRUNCATE = 30


class _HtmlSimplifier(HTMLParser):
    """Strip HTML to structural skeleton: tags + key attributes, truncated text."""

    def __init__(self, max_length: int):
        super().__init__()
        self._max = max_length
        self._parts: list[str] = []
        self._length = 0
        self._skip_depth = 0

    def _append(self, s: str):
        if self._length >= self._max:
            return
        remaining = self._max - self._length
        chunk = s[:remaining]
        self._parts.append(chunk)
        self._length += len(chunk)

    def handle_starttag(self, tag, attrs):
        if tag in _REMOVE_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return
        kept = [(k, v) for k, v in attrs if k in _KEEP_ATTRS and v]
        attr_str = " ".join(f'{k}="{v}"' for k, v in kept)
        self._append(f"<{tag} {attr_str}>" if attr_str else f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in _REMOVE_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth > 0:
            return
        self._append(f"</{tag}>")

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        text = data.strip()
        if not text:
            return
        if len(text) > _TEXT_TRUNCATE:
            text = text[:_TEXT_TRUNCATE] + "…"
        self._append(text)

    def get_result(self) -> str:
        return "".join(self._parts)


def simplify_html(html: str, max_length: int = 4000) -> str:
    """Simplify HTML to a structural skeleton for LLM analysis."""
    if not html:
        return ""
    parser = _HtmlSimplifier(max_length)
    try:
        parser.feed(html)
    except Exception:
        pass
    return parser.get_result()


class ListingAnalyzer:
    """Uses LLM to analyze a listing page and determine how to extract job cards."""

    def __init__(self, llm_client):
        self._llm = llm_client

    async def analyze_page(
        self, page_text: str, page_url: str, html_snippet: str
    ) -> PagePattern:
        """Call LLM to analyze the listing page, return a PagePattern."""
        messages = build_analyze_listing_messages(page_text, page_url, html_snippet)
        result = await self._llm.structured_parse(messages)

        return PagePattern(
            job_links=result.get("job_links", []),
            job_card_selector=result.get("job_card_selector"),
            card_strategy=result.get("card_strategy", "href"),
            next_button_selector=result.get("next_button_selector"),
            page_number_selector=result.get("page_number_selector"),
            confidence=result.get("confidence", 0.0),
        )
