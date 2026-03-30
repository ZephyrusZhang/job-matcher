"""Playwright browser management for page rendering.

Key invariant: the listing page always stays in the FIRST tab.
Detail pages are opened in new tabs and closed after collection.
Pagination clicks happen on the listing tab and never open new tabs.
"""

import logging
from urllib.parse import urljoin

from playwright.async_api import Page, async_playwright

from app.config import CrawlConfig

logger = logging.getLogger(__name__)


class PageContext:
    """Snapshot of a listing page for agent analysis."""

    __slots__ = ("url", "text", "html_snippet")

    def __init__(self, url: str, text: str, html_snippet: str):
        self.url = url
        self.text = text
        self.html_snippet = html_snippet


class BrowserManager:
    def __init__(self, config: CrawlConfig):
        self._config = config
        self._playwright = None
        self._browser = None

    async def init(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._config.browser_headless,
            args=["--no-proxy-server"],
        )
        logger.info("Browser initialized (headless=%s)", self._config.browser_headless)

    # ── Page lifecycle ──────────────────────────────────────

    async def open_page(self, url: str) -> Page:
        page = await self._browser.new_page()
        await self._navigate(page, url)
        return page

    async def close_page(self, page: Page):
        await page.close()

    async def _navigate(self, page: Page, url: str):
        await page.goto(url, timeout=self._config.page_load_timeout)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

    async def wait_for_selector(self, page: Page, selector: str, timeout: int = 10000):
        """Wait for at least one element matching selector to appear."""
        try:
            await page.wait_for_selector(selector, timeout=timeout)
        except Exception:
            pass  # Timeout is acceptable — page might not have the element

    # ── Page analysis ───────────────────────────────────────

    async def scroll_to_bottom(self, page: Page):
        for _ in range(self._config.max_scroll_attempts):
            prev_height = await page.evaluate("document.body.scrollHeight")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == prev_height:
                break

    async def get_page_context(self, page: Page) -> PageContext:
        """Analyze the DOM via JS and return structured info for the agent."""
        text = await page.evaluate("() => document.body?.innerText?.slice(0, 3000) || ''")

        dom_analysis = await page.evaluate("""() => {
            const result = {linkGroups: [], repeatingElements: [], pagination: null};

            const links = document.querySelectorAll('a[href]');
            const linkMap = {};
            links.forEach(a => {
                const cls = a.className.trim().split(/\\s+/).sort().join('.');
                const tag = 'a' + (cls ? '.' + cls : '');
                if (!linkMap[tag]) linkMap[tag] = {selector: tag, count: 0, hrefs: []};
                linkMap[tag].count++;
                if (linkMap[tag].hrefs.length < 5) linkMap[tag].hrefs.push(a.getAttribute('href'));
            });
            result.linkGroups = Object.values(linkMap)
                .filter(g => g.count >= 2)
                .sort((a, b) => b.count - a.count)
                .slice(0, 15);

            const containers = document.querySelectorAll('li, div, article, section, tr');
            const clsCount = {};
            containers.forEach(el => {
                if (!el.className) return;
                const first = el.className.trim().split(/\\s+/)[0];
                if (!first) return;
                const sel = el.tagName.toLowerCase() + '.' + first;
                if (!clsCount[sel]) clsCount[sel] = {selector: sel, count: 0, sample: ''};
                clsCount[sel].count++;
                if (!clsCount[sel].sample) clsCount[sel].sample = el.outerHTML.slice(0, 300);
            });
            result.repeatingElements = Object.values(clsCount)
                .filter(g => g.count >= 3)
                .sort((a, b) => b.count - a.count)
                .slice(0, 15);

            // Find all pagination-like elements, pick the best one
            const pagCandidates = document.querySelectorAll(
                '[class*="page"], [class*="paginat"], nav ul'
            );
            let bestPag = null;
            let bestScore = 0;
            pagCandidates.forEach(el => {
                const text = el.textContent || '';
                const cls = el.className || '';
                // Skip swiper/carousel pagination (not list pagination)
                if (cls.includes('swiper') || cls.includes('carousel') || cls.includes('slider')) return;
                // Score by how many page numbers it contains
                const nums = text.match(/\\b\\d+\\b/g) || [];
                const hasArrow = /[>›»]|下一页|next/i.test(text);
                const score = nums.length + (hasArrow ? 5 : 0);
                if (score > bestScore) {
                    bestScore = score;
                    bestPag = el;
                }
            });
            if (bestPag) result.pagination = bestPag.outerHTML.slice(0, 3000);

            return result;
        }""")

        lines = [f"URL: {page.url}", ""]
        lines.append("=== 重复出现的链接组（可能是岗位链接） ===")
        for g in dom_analysis.get("linkGroups", []):
            lines.append(f"  选择器: {g['selector']}  (出现 {g['count']} 次)")
            for href in g["hrefs"][:3]:
                lines.append(f"    href: {href}")
        lines.append("")
        lines.append("=== 重复出现的容器元素（可能是岗位卡片） ===")
        for g in dom_analysis.get("repeatingElements", []):
            lines.append(f"  选择器: {g['selector']}  (出现 {g['count']} 次)")
            lines.append(f"    样例HTML: {g['sample'][:200]}")
        lines.append("")
        lines.append("=== 分页组件 ===")
        pag = dom_analysis.get("pagination")
        lines.append(pag[:300] if pag else "未检测到分页组件")

        return PageContext(url=page.url, text=text, html_snippet="\n".join(lines))

    # ── Detail collection ───────────────────────────────────

    async def collect_details_by_links(
        self, page: Page, links: list[str]
    ) -> list[tuple[str, str]]:
        """Open each link in a NEW tab, collect (html, url), close tab."""
        base_url = page.url
        results = []
        for link in links:
            absolute = urljoin(base_url, link)
            detail_page = None
            try:
                detail_page = await page.context.new_page()
                await self._navigate(detail_page, absolute)
                results.append((await detail_page.content(), detail_page.url))
            except Exception:
                logger.warning("Failed to load: %s", absolute)
            finally:
                if detail_page:
                    await detail_page.close()
        return results

    async def collect_details_by_selector(
        self, page: Page, selector: str, strategy: str = "auto"
    ) -> list[tuple[str, str]]:
        """Find job cards, collect detail pages. Returns (html, url) tuples."""
        # Wait for cards to be present in DOM before querying
        try:
            await page.wait_for_selector(selector, timeout=10000)
        except Exception:
            pass
        cards = await page.query_selector_all(selector)
        logger.info("Found %d cards with selector: %s", len(cards), selector)
        if not cards:
            return []

        if strategy == "auto":
            first_tag = await cards[0].evaluate("el => el.tagName.toLowerCase()")
            first_href = await cards[0].get_attribute("href")
            strategy = "href" if first_tag == "a" and first_href else "click"

        if strategy == "href":
            return await self._collect_via_links(page, cards)
        else:
            return await self._collect_via_clicks(page, cards, selector)

    async def _collect_via_links(self, page: Page, cards) -> list[tuple[str, str]]:
        """Extract hrefs from <a> cards, open each in a new tab."""
        listing_url = page.url.rstrip("/")
        listing_path = listing_url.split("?")[0]

        hrefs = []
        seen = set()
        for card in cards:
            href = await card.get_attribute("href")
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            absolute = urljoin(listing_url, href)
            abs_path = absolute.split("?")[0].rstrip("/")
            if abs_path == listing_path or len(abs_path) <= len(listing_path):
                continue
            if absolute not in seen:
                seen.add(absolute)
                hrefs.append(absolute)

        return await self.collect_details_by_links(page, hrefs)

    async def _click_and_get_new_tab(self, page: Page, element) -> Page | None:
        """Click an element and wait for a new tab to open.

        Uses Playwright's expect_page() which listens for the 'page' event
        internally — starts listening BEFORE the click, so it never misses
        the new tab. Returns None only if no new tab opens within timeout.
        """
        context = page.context
        try:
            # expect_page starts listening immediately, then we click
            async with context.expect_page(timeout=10000) as page_event:
                await element.click()
            new_tab = await page_event.value
            # Wait for the new tab to fully load
            await new_tab.wait_for_load_state("load", timeout=15000)
            return new_tab
        except TimeoutError:
            # Playwright timeout — no new tab opened
            return None
        except Exception:
            # Other errors (element detached, etc.)
            return None

    async def _collect_via_clicks(self, page: Page, cards, selector: str) -> list[tuple[str, str]]:
        """Click each card, collect detail in a new tab immediately, close tab.

        Per card:
        1. Click card (expect_page listens for new tab)
        2. If new tab opened → wait for load, collect, close
        3. If no new tab → check same-page navigation
        """
        listing_url = page.url
        total = len(cards)
        results = []

        for i in range(total):
            try:
                current_cards = await page.query_selector_all(selector)
                if i >= len(current_cards):
                    break
                card = current_cards[i]

                new_tab = await self._click_and_get_new_tab(page, card)

                if new_tab is not None:
                    try:
                        await new_tab.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    results.append((await new_tab.content(), new_tab.url))
                    await new_tab.close()

                elif page.url != listing_url:
                    detail_url = page.url
                    await self._navigate(page, listing_url)
                    await self.scroll_to_bottom(page)

                    detail_page = await page.context.new_page()
                    try:
                        await self._navigate(detail_page, detail_url)
                        results.append((await detail_page.content(), detail_page.url))
                    except Exception:
                        logger.warning("Failed to load: %s", detail_url)
                    finally:
                        await detail_page.close()

                else:
                    logger.warning("Card %d/%d: no navigation, skipping", i + 1, total)
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(500)

            except Exception:
                logger.warning("Failed on card %d/%d", i + 1, total)
                # Clean up leaked tabs
                await self.close_other_tabs(page)

        return results

    async def close_other_tabs(self, keep: Page):
        """Close all tabs except the one to keep."""
        for p in keep.context.pages:
            if p != keep:
                try:
                    await p.close()
                except Exception:
                    pass

    # ── Pagination ──────────────────────────────────────────

    async def go_next_page(
        self,
        page: Page,
        current_page: int,
        next_button_selector: str | None = None,
        page_number_selector: str | None = None,
    ) -> bool:
        """Navigate to next listing page. All clicks happen on the same tab.

        Returns True if successfully navigated to next page.
        """
        # Strategy 1: click "下一页" button
        if next_button_selector:
            if await self._click_pagination_element(page, next_button_selector):
                logger.info("Next page via next-button: %s", next_button_selector)
                return True

        # Strategy 2: click page number N+1
        if page_number_selector:
            if await self._click_page_number(page, current_page, page_number_selector):
                return True

        # Strategy 3: generic fallback
        if await self._go_next_by_arrow(page):
            return True

        logger.info("No next page found after page %d", current_page)
        return False

    async def _click_pagination_element(self, page: Page, selector: str) -> bool:
        """Click a pagination element by CSS selector on the current tab."""
        try:
            btn = await page.query_selector(selector)
            if btn:
                is_disabled = await btn.evaluate(
                    """el => el.disabled
                    || el.classList.contains('disabled')
                    || el.getAttribute('aria-disabled') === 'true'"""
                )
                if not is_disabled:
                    await btn.click()
                    try:
                        await page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    return True
        except Exception:
            pass
        return False

    async def _click_page_number(
        self, page: Page, current_page: int, selector: str
    ) -> bool:
        """Click the N+1 page number among elements matching selector."""
        next_text = str(current_page + 1)
        try:
            elements = await page.query_selector_all(selector)
            for el in elements:
                text = await el.evaluate("el => el.textContent.trim()")
                if text == next_text:
                    is_disabled = await el.evaluate(
                        """el => el.disabled
                        || el.classList.contains('disabled')
                        || el.getAttribute('aria-disabled') === 'true'"""
                    )
                    if is_disabled:
                        continue
                    await el.click()
                    try:
                        await page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    logger.info("Next page via number: %s → %s", selector, next_text)
                    return True
        except Exception:
            pass
        return False

    async def _go_next_by_arrow(self, page: Page) -> bool:
        """Try common next-page selectors and arrow text."""
        for sel in [
            'a[aria-label="Next"]', 'button[aria-label="Next"]',
            'a[aria-label="next"]', 'li.next > a', 'a.next',
            'button.next', '[class*="next"]:not([class*="disabled"])',
        ]:
            if await self._click_pagination_element(page, sel):
                logger.info("Next page via arrow selector: %s", sel)
                return True

        for arrow_text in [">", "›", "»", "下一页"]:
            try:
                locator = page.get_by_text(arrow_text, exact=True)
                count = await locator.count()
                for i in range(count):
                    el = locator.nth(i)
                    tag = await el.evaluate("el => el.tagName.toLowerCase()")
                    if tag not in ("a", "button", "li", "span", "div"):
                        continue
                    is_disabled = await el.evaluate(
                        """el => {
                            const p = el.closest('[class*="disabled"]');
                            return el.disabled || el.classList.contains('disabled')
                                || el.getAttribute('aria-disabled') === 'true'
                                || p !== null;
                        }"""
                    )
                    if is_disabled:
                        continue
                    await el.click()
                    try:
                        await page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    logger.info("Next page via arrow text: %s", arrow_text)
                    return True
            except Exception:
                continue
        return False

    # ── Cleanup ─────────────────────────────────────────────

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
