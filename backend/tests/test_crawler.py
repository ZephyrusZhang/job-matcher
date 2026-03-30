"""Tests for crawler module: dedup, pipeline, scheduler."""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


class TestDedup:
    def test_compute_content_hash(self):
        from app.crawl.dedup import compute_content_hash

        h1 = compute_content_hash("前端工程师", "负责前端开发", "熟悉React和TypeScript")
        h2 = compute_content_hash("前端工程师", "负责前端开发", "熟悉React和TypeScript")
        h3 = compute_content_hash("后端工程师", "负责后端开发", "熟悉Java和Go")
        assert h1 == h2  # Same input → same hash
        assert h1 != h3  # Different input → different hash

    def test_content_hash_deterministic(self):
        """Same text should always produce same hash."""
        from app.crawl.dedup import compute_content_hash

        h1 = compute_content_hash("Job", "Desc", "1、熟悉React；2、熟悉TypeScript")
        h2 = compute_content_hash("Job", "Desc", "1、熟悉React；2、熟悉TypeScript")
        assert h1 == h2

    async def test_upsert_new_jobs(self, db):
        """New jobs should be inserted."""
        from app.crawl.dedup import upsert_jobs

        jobs = [
            {
                "title": "前端工程师",
                "category": "前端",
                "location": "北京",
                "job_type": "fulltime",
                "responsibilities": "负责前端开发",
                "requirements": "1、熟悉React和TypeScript；2、了解GraphQL优先",
                "department": "前端团队",
                "department_product": "抖音",
                "education": "本科",
                "experience": "2年",
                "posted_date": "2026-03-01",
                "source_url": "https://example.com/job1",
                "summary": "前端开发",
            }
        ]
        result = await upsert_jobs(db, jobs, "test_company")
        assert result["jobs_found"] == 1
        assert result["jobs_new"] == 1
        assert result["jobs_updated"] == 0

        # Verify in DB
        rows = await db.fetch_all("SELECT * FROM jobs WHERE company_id = 'test_company'")
        assert len(rows) == 1
        assert rows[0]["title"] == "前端工程师"

    async def test_upsert_duplicate_skipped(self, db):
        """Jobs with same content hash should be skipped."""
        from app.crawl.dedup import upsert_jobs

        job = {
            "title": "前端工程师",
            "category": "前端",
            "location": "北京",
            "job_type": "fulltime",
            "responsibilities": "负责前端开发",
            "requirements": "1、熟悉React",
            "department": None,
            "department_product": None,
            "education": None,
            "experience": None,
            "posted_date": None,
            "source_url": "https://example.com/job1",
            "summary": None,
        }
        await upsert_jobs(db, [job], "test_company")
        result = await upsert_jobs(db, [job], "test_company")
        assert result["jobs_new"] == 0
        assert result["jobs_updated"] == 0

    async def test_upsert_updated_job(self, db):
        """Job with same hash but changed fields should be updated."""
        from app.crawl.dedup import upsert_jobs

        job1 = {
            "title": "前端工程师",
            "category": "前端",
            "location": "北京",
            "job_type": "fulltime",
            "responsibilities": "负责前端开发",
            "requirements": "1、熟悉React",
            "department": None,
            "department_product": None,
            "education": None,
            "experience": None,
            "posted_date": None,
            "source_url": "https://example.com/job1",
            "summary": None,
        }
        await upsert_jobs(db, [job1], "test_company")

        # Same core content but different location → same hash, but location changed
        job2 = {**job1, "location": "上海"}
        result = await upsert_jobs(db, [job2], "test_company")
        assert result["jobs_updated"] == 1

        row = await db.fetch_one("SELECT location FROM jobs WHERE company_id = 'test_company'")
        assert row["location"] == "上海"


class TestBrowserManager:
    async def test_init_and_close(self):
        """BrowserManager should init and close without errors when mocked."""
        from app.crawl.browser import BrowserManager
        from app.config import CrawlConfig

        config = CrawlConfig()
        manager = BrowserManager(config)

        with patch("app.crawl.browser.async_playwright") as mock_pw:
            mock_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_instance.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_pw.return_value.start = AsyncMock(return_value=mock_instance)

            await manager.init()
            assert manager._browser is not None
            await manager.close()

    async def test_get_page_context(self):
        """get_page_context should return text + DOM analysis."""
        from app.crawl.browser import BrowserManager
        from app.config import CrawlConfig

        manager = BrowserManager(CrawlConfig())

        mock_page = AsyncMock()
        mock_page.url = "https://example.com/jobs"
        # First evaluate call returns text, second returns DOM analysis dict
        mock_page.evaluate = AsyncMock(side_effect=[
            "Frontend Dev\nBeijing",  # innerText
            {  # DOM analysis
                "linkGroups": [
                    {"selector": "a.job-link", "count": 10, "hrefs": ["/job/1", "/job/2"]},
                ],
                "repeatingElements": [
                    {"selector": "li.job-card", "count": 10, "sample": "<li class='job-card'>..."},
                ],
                "pagination": '<nav class="pages"><a>2</a></nav>',
            },
        ])

        ctx = await manager.get_page_context(mock_page)
        assert ctx.url == "https://example.com/jobs"
        assert "Frontend Dev" in ctx.text
        assert "a.job-link" in ctx.html_snippet
        assert "li.job-card" in ctx.html_snippet

    async def test_collect_details_by_links(self):
        """Should open each link in a new tab and collect HTML."""
        from app.crawl.browser import BrowserManager
        from app.config import CrawlConfig

        manager = BrowserManager(CrawlConfig())

        # Mock the detail tab opened via context.new_page()
        mock_detail_page = AsyncMock()
        mock_detail_page.content = AsyncMock(return_value="<html>detail</html>")
        mock_detail_page.url = "https://example.com/job/1"
        mock_detail_page.goto = AsyncMock()
        mock_detail_page.wait_for_load_state = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_detail_page)

        mock_listing_page = AsyncMock()
        mock_listing_page.url = "https://example.com/jobs"
        mock_listing_page.context = mock_context

        result = await manager.collect_details_by_links(
            mock_listing_page, ["/job/1", "/job/2"]
        )
        assert len(result) == 2
        # Each result is a (html, url) tuple
        assert result[0] == ("<html>detail</html>", "https://example.com/job/1")
        assert mock_detail_page.close.call_count == 2

    async def test_collect_details_by_selector_href(self):
        """href strategy: extract hrefs from <a> cards, open in new tabs."""
        from app.crawl.browser import BrowserManager
        from app.config import CrawlConfig

        manager = BrowserManager(CrawlConfig())

        mock_link = AsyncMock()
        mock_link.get_attribute = AsyncMock(return_value="/jobs/123/detail")
        mock_link.evaluate = AsyncMock(return_value="a")

        mock_detail_page = AsyncMock()
        mock_detail_page.content = AsyncMock(return_value="<html>detail</html>")
        mock_detail_page.url = "https://example.com/jobs/123/detail"
        mock_detail_page.goto = AsyncMock()
        mock_detail_page.wait_for_load_state = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_detail_page)

        mock_page = AsyncMock()
        mock_page.url = "https://example.com/jobs"
        mock_page.context = mock_context
        mock_page.query_selector_all = AsyncMock(return_value=[mock_link])

        result = await manager.collect_details_by_selector(mock_page, "a.job", "auto")
        assert len(result) == 1
        assert result[0] == ("<html>detail</html>", "https://example.com/jobs/123/detail")
        mock_detail_page.close.assert_called_once()

    async def test_go_next_page_by_button_selector(self):
        """Primary: should use next_button_selector first."""
        from app.crawl.browser import BrowserManager
        from app.config import CrawlConfig

        manager = BrowserManager(CrawlConfig())

        mock_btn = AsyncMock()
        mock_btn.evaluate = AsyncMock(return_value=False)

        mock_page = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=mock_btn)
        mock_page.wait_for_load_state = AsyncMock()

        result = await manager.go_next_page(mock_page, 1, next_button_selector="a.next-btn")
        assert result is True
        mock_btn.click.assert_called_once()

    async def test_go_next_page_by_page_number_selector(self):
        """Fallback: should use page_number_selector to click page N+1."""
        from app.crawl.browser import BrowserManager
        from app.config import CrawlConfig

        manager = BrowserManager(CrawlConfig())

        mock_el_1 = AsyncMock()
        mock_el_1.evaluate = AsyncMock(side_effect=["1", False])
        mock_el_2 = AsyncMock()
        mock_el_2.evaluate = AsyncMock(side_effect=["2", False])

        mock_page = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[mock_el_1, mock_el_2])
        mock_page.query_selector = AsyncMock(return_value=None)
        mock_page.wait_for_load_state = AsyncMock()

        result = await manager.go_next_page(mock_page, 1, page_number_selector="li.number")
        assert result is True
        mock_el_2.click.assert_called_once()

    async def test_go_next_page_fallback_to_arrow(self):
        """When both selectors fail, fall back to generic '>' arrow."""
        from app.crawl.browser import BrowserManager
        from app.config import CrawlConfig

        manager = BrowserManager(CrawlConfig())

        mock_arrow = AsyncMock()
        mock_arrow.evaluate = AsyncMock(side_effect=["a", False])

        mock_arrow_locator = AsyncMock()
        mock_arrow_locator.count = AsyncMock(return_value=1)
        mock_arrow_locator.nth = MagicMock(return_value=mock_arrow)

        mock_empty_locator = AsyncMock()
        mock_empty_locator.count = AsyncMock(return_value=0)

        mock_page = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)
        mock_page.query_selector_all = AsyncMock(return_value=[])
        mock_page.get_by_text = MagicMock(side_effect=lambda text, **kw: (
            mock_arrow_locator if text == ">" else mock_empty_locator
        ))
        mock_page.wait_for_load_state = AsyncMock()

        result = await manager.go_next_page(mock_page, 5)
        assert result is True
        mock_arrow.click.assert_called_once()


class TestContentExtractor:
    async def test_extract_returns_text_list(self):
        """Extractor should return list of text strings."""
        from app.crawl.extractor import ContentExtractor

        extractor = ContentExtractor()
        html_pages = ["<html><body><p>Job description here</p></body></html>"]

        with patch("app.crawl.extractor.AsyncWebCrawler") as MockCrawler:
            mock_instance = AsyncMock()
            mock_result = MagicMock()
            mock_result.markdown = "Job description here"
            mock_instance.arun = AsyncMock(return_value=mock_result)
            MockCrawler.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            MockCrawler.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await extractor.extract(html_pages)
            assert isinstance(results, list)
            assert len(results) == 1


class TestCrawlScheduler:
    def test_scheduler_registers_jobs(self):
        """Scheduler should register a job per company."""
        from app.crawl.scheduler import CrawlScheduler
        from app.config import CompanyConfig

        companies = [
            CompanyConfig(id="c1", name="Company1", career_url="https://a.com", crawl_interval_hours=12),
            CompanyConfig(id="c2", name="Company2", career_url="https://b.com", crawl_interval_hours=24),
        ]
        scheduler = CrawlScheduler(companies)

        with patch.object(scheduler._scheduler, "add_job") as mock_add:
            with patch.object(scheduler._scheduler, "start"):
                scheduler.start(crawl_func=AsyncMock())
                assert mock_add.call_count == 2

    def test_scheduler_stop(self):
        """Scheduler stop should not error."""
        from app.crawl.scheduler import CrawlScheduler

        scheduler = CrawlScheduler([])
        with patch.object(scheduler._scheduler, "shutdown"):
            scheduler.stop()


class TestPipeline:
    def _make_mock_browser(self):
        """Create a mock browser with fine-grained methods."""
        mock = AsyncMock()
        mock.open_page = AsyncMock(return_value=AsyncMock())
        mock.close_page = AsyncMock()
        mock.scroll_to_bottom = AsyncMock()
        mock._navigate = AsyncMock()
        mock.go_next_page = AsyncMock(return_value=False)  # single page by default
        return mock

    def _make_job_response(self, title="Job"):
        return {"jobs": [{
            "title": title, "category": "后端", "source_url": "https://test.com/1",
            "responsibilities": "dev", "requirements": "Python",
        }]}

    async def test_pipeline_with_hint_selector(self):
        """Company with job_card_selector hint should skip agent, use selector directly."""
        from app.crawl.pipeline import crawl_company
        from app.config import CompanyConfig

        company = CompanyConfig(
            id="test", name="测试", career_url="https://test.com",
            crawl_interval_hours=24, max_pages=1,
            job_card_selector="a.job-link",  # hint provided
        )

        mock_browser = self._make_mock_browser()
        mock_browser.collect_details_by_selector = AsyncMock(return_value=[("<html>detail</html>", "https://test.com/job/1")])

        mock_extractor = AsyncMock()
        mock_extractor.extract = AsyncMock(return_value=["这是一个足够长的岗位描述文本，包含职位描述和职位要求，需要超过50个字符才能通过非空过滤，所以我们写一段比较长的文字在这里"])

        mock_llm = AsyncMock()
        mock_llm.structured_parse = AsyncMock(return_value=self._make_job_response())

        mock_db = AsyncMock()

        with patch("app.crawl.pipeline.upsert_jobs", new_callable=AsyncMock) as mock_upsert:
            mock_upsert.return_value = {"jobs_found": 1, "jobs_new": 1, "jobs_updated": 0}
            result = await crawl_company(
                company=company, browser=mock_browser,
                extractor=mock_extractor, llm_client=mock_llm, db=mock_db,
            )
            assert result["jobs_found"] == 1
            # Should have used collect_details_by_selector with the hint
            mock_browser.collect_details_by_selector.assert_called()
            call_args = mock_browser.collect_details_by_selector.call_args
            assert call_args[0][1] == "a.job-link"
            # Agent structured_parse called for job parsing, NOT for page analysis
            # (parse_job prompt, not analyze_listing prompt)

    async def test_pipeline_with_agent(self):
        """Without hint, agent should analyze page and return selectors."""
        from app.crawl.pipeline import crawl_company
        from app.config import CompanyConfig, CrawlConfig

        company = CompanyConfig(
            id="test", name="测试", career_url="https://test.com",
            crawl_interval_hours=24, max_pages=1,
            job_card_selector="",  # no hint
        )

        mock_browser = self._make_mock_browser()
        mock_browser.get_page_context = AsyncMock(
            return_value=MagicMock(url="https://test.com", text="Jobs", html_snippet="<div/>")
        )
        mock_browser.collect_details_by_links = AsyncMock(return_value=[("<html>detail</html>", "https://test.com/job/1")])

        mock_extractor = AsyncMock()
        mock_extractor.extract = AsyncMock(return_value=["这是一个足够长的岗位描述文本，包含职位描述和职位要求，需要超过50个字符才能通过非空过滤，所以我们写一段比较长的文字在这里"])

        # LLM returns: first call = agent analysis, second call = job parse
        mock_llm = AsyncMock()
        mock_llm.structured_parse = AsyncMock(side_effect=[
            # Agent analysis response
            {
                "job_links": ["https://test.com/job/1"],
                "job_card_selector": "a.job",
                "card_strategy": "href",
                "next_button_selector": None, "page_number_selector": None,
                "confidence": 0.9,
            },
            # Job parse response
            self._make_job_response(),
        ])

        mock_db = AsyncMock()

        with patch("app.crawl.pipeline.upsert_jobs", new_callable=AsyncMock) as mock_upsert:
            mock_upsert.return_value = {"jobs_found": 1, "jobs_new": 1, "jobs_updated": 0}
            result = await crawl_company(
                company=company, browser=mock_browser,
                extractor=mock_extractor, llm_client=mock_llm, db=mock_db,
                crawl_config=CrawlConfig(),
            )
            assert result["jobs_found"] == 1
            # Agent should have called get_page_context
            mock_browser.get_page_context.assert_called_once()
            # Should use collect_details_by_links since agent returned links
            mock_browser.collect_details_by_links.assert_called_once()

    async def test_pipeline_agent_locks_after_consistent_pages(self):
        """Agent analyzes only page 1, locks immediately, pages 2-3 use locked selector."""
        from app.crawl.pipeline import crawl_company
        from app.config import CompanyConfig, CrawlConfig

        company = CompanyConfig(
            id="test", name="测试", career_url="https://test.com",
            crawl_interval_hours=24, max_pages=3,
            job_card_selector="",
        )

        mock_browser = self._make_mock_browser()
        mock_browser.go_next_page = AsyncMock(side_effect=[True, True, False])
        mock_browser.get_page_context = AsyncMock(
            return_value=MagicMock(url="https://test.com", text="Jobs", html_snippet="<div/>")
        )
        mock_browser.collect_details_by_links = AsyncMock(return_value=[("<html>d</html>", "https://test.com/job/1")])
        mock_browser.collect_details_by_selector = AsyncMock(return_value=[("<html>d</html>", "https://test.com/job/1")])
        mock_browser.wait_for_selector = AsyncMock()

        mock_extractor = AsyncMock()
        mock_extractor.extract = AsyncMock(return_value=["这是一个足够长的岗位描述文本，包含职位描述和职位要求，需要超过50个字符才能通过非空过滤，所以我们写一段比较长的文字在这里"])

        agent_response = {
            "job_links": ["/job/1"], "job_card_selector": "a.job",
            "card_strategy": "href", "next_button_selector": None, "page_number_selector": None, "confidence": 0.9,
        }
        mock_llm = AsyncMock()
        mock_llm.structured_parse = AsyncMock(side_effect=[
            agent_response,              # page 1 agent analysis → locks!
            self._make_job_response(),   # page 1 parse
            self._make_job_response(),   # page 2 parse (locked, no agent)
            self._make_job_response(),   # page 3 parse (locked, no agent)
        ])

        mock_db = AsyncMock()

        with patch("app.crawl.pipeline.upsert_jobs", new_callable=AsyncMock) as mock_upsert:
            mock_upsert.return_value = {"jobs_found": 3, "jobs_new": 3, "jobs_updated": 0}
            result = await crawl_company(
                company=company, browser=mock_browser,
                extractor=mock_extractor, llm_client=mock_llm, db=mock_db,
                crawl_config=CrawlConfig(agent_learning_pages=1, agent_lock_threshold=1),
            )
            assert result["jobs_found"] == 3
            # Agent only called once (page 1)
            assert mock_browser.get_page_context.call_count == 1
            # Pages 2-3 use locked selector
            assert mock_browser.collect_details_by_selector.call_count >= 2

    async def test_pipeline_fallback_on_agent_failure(self):
        """If agent fails, pipeline should fallback to default selector."""
        from app.crawl.pipeline import crawl_company
        from app.config import CompanyConfig, CrawlConfig

        company = CompanyConfig(
            id="test", name="测试", career_url="https://test.com",
            crawl_interval_hours=24, max_pages=1,
            job_card_selector="",
        )

        mock_browser = self._make_mock_browser()
        mock_browser.get_page_context = AsyncMock(side_effect=RuntimeError("failed"))
        mock_browser.collect_details_by_selector = AsyncMock(return_value=[("<html>d</html>", "https://test.com/job/1")])

        mock_extractor = AsyncMock()
        mock_extractor.extract = AsyncMock(return_value=["这是一个足够长的岗位描述文本，包含职位描述和职位要求，需要超过50个字符才能通过非空过滤，所以我们写一段比较长的文字在这里"])

        mock_llm = AsyncMock()
        mock_llm.structured_parse = AsyncMock(return_value=self._make_job_response())

        mock_db = AsyncMock()

        with patch("app.crawl.pipeline.upsert_jobs", new_callable=AsyncMock) as mock_upsert:
            mock_upsert.return_value = {"jobs_found": 1, "jobs_new": 1, "jobs_updated": 0}
            result = await crawl_company(
                company=company, browser=mock_browser,
                extractor=mock_extractor, llm_client=mock_llm, db=mock_db,
                crawl_config=CrawlConfig(),
            )
            assert result["jobs_found"] == 1
            # Should have fallen back to default selector
            mock_browser.collect_details_by_selector.assert_called()
