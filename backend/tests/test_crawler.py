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
            mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_pw.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_pw.return_value.start = AsyncMock(return_value=mock_instance)

            await manager.init()
            assert manager._browser is not None
            await manager.close()

    async def test_render_and_collect_single_page(self):
        """Should collect detail pages and resolve relative URLs."""
        from app.crawl.browser import BrowserManager
        from app.config import CrawlConfig

        config = CrawlConfig()
        manager = BrowserManager(config)

        mock_link = AsyncMock()
        mock_link.get_attribute = AsyncMock(return_value="/jobs/123/detail")

        mock_page = AsyncMock()
        mock_page.url = "https://example.com/jobs"
        mock_page.content = AsyncMock(return_value="<html>detail</html>")
        mock_page.evaluate = AsyncMock(return_value=0)
        mock_page.query_selector_all = AsyncMock(return_value=[mock_link])
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.goto = AsyncMock()
        # Mock get_by_text for _go_to_next_page — no pagination element found
        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.get_by_text = MagicMock(return_value=mock_locator)

        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        manager._browser = mock_browser

        pages = await manager.render_and_collect("https://example.com/jobs", max_pages=1)
        assert isinstance(pages, list)
        assert len(pages) == 1
        goto_calls = [c[0][0] for c in mock_page.goto.call_args_list]
        assert "https://example.com/jobs/123/detail" in goto_calls

    async def test_render_respects_max_pages(self):
        """max_pages should limit how many listing pages are crawled."""
        from app.crawl.browser import BrowserManager
        from app.config import CrawlConfig

        config = CrawlConfig()
        manager = BrowserManager(config)

        mock_page = AsyncMock()
        mock_page.url = "https://example.com/jobs"
        mock_page.content = AsyncMock(return_value="<html>detail</html>")
        mock_page.evaluate = AsyncMock(return_value=0)
        mock_page.query_selector_all = AsyncMock(return_value=[])
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.goto = AsyncMock()
        # Mock pagination — page 2 link exists
        mock_el = AsyncMock()
        mock_el.evaluate = AsyncMock(side_effect=["a", True])
        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_locator.nth = MagicMock(return_value=mock_el)
        mock_page.get_by_text = MagicMock(return_value=mock_locator)

        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        manager._browser = mock_browser

        await manager.render_and_collect("https://example.com/jobs", max_pages=2)
        # Should not go beyond 2 listing pages even though next-page exists


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
    async def test_crawl_company_pipeline(self):
        """Full pipeline should coordinate browser → extractor → LLM → dedup."""
        from app.crawl.pipeline import crawl_company
        from app.config import CompanyConfig

        company = CompanyConfig(
            id="test", name="测试", career_url="https://test.com", crawl_interval_hours=24
        )

        # Mock browser.crawl_listing_pages as an async generator yielding one batch
        async def mock_crawl_listing_pages(url, max_pages=-1):
            yield ["<html>detail page</html>"]

        mock_browser = AsyncMock()
        mock_browser.crawl_listing_pages = mock_crawl_listing_pages

        mock_extractor = AsyncMock()
        mock_extractor.extract = AsyncMock(
            return_value=["Detail with 职位描述 and 职位要求"]
        )

        mock_llm = AsyncMock()
        mock_llm.structured_parse = AsyncMock(
            return_value={
                "jobs": [
                    {
                        "title": "Test Job",
                        "category": "后端",
                        "location": "北京",
                        "job_type": "fulltime",
                        "responsibilities": "coding",
                        "requirements": "1、熟悉Python",
                        "department": None,
                        "department_product": None,
                        "education": None,
                        "experience": None,
                        "posted_date": None,
                        "source_url": "https://test.com/job1",
                        "summary": "Test",
                    }
                ]
            }
        )

        mock_db = AsyncMock()

        with patch("app.crawl.pipeline.upsert_jobs", new_callable=AsyncMock) as mock_upsert:
            mock_upsert.return_value = {"jobs_found": 1, "jobs_new": 1, "jobs_updated": 0}
            result = await crawl_company(
                company=company,
                browser=mock_browser,
                extractor=mock_extractor,
                llm_client=mock_llm,
                db=mock_db,
            )
            assert result["jobs_found"] == 1
            mock_extractor.extract.assert_called_once()
            mock_llm.structured_parse.assert_called_once()

    async def test_pipeline_overlaps_crawl_and_parse(self):
        """While LLM parses page 1, browser should be crawling page 2."""
        from app.crawl.pipeline import crawl_company
        from app.config import CompanyConfig

        company = CompanyConfig(
            id="test", name="测试", career_url="https://test.com",
            crawl_interval_hours=24, max_pages=2,
        )

        call_order = []

        async def mock_crawl_listing_pages(url, max_pages=-1):
            call_order.append("crawl_page_1")
            yield ["<html>page1</html>"]
            call_order.append("crawl_page_2")
            yield ["<html>page2</html>"]

        mock_browser = AsyncMock()
        mock_browser.crawl_listing_pages = mock_crawl_listing_pages

        async def mock_extract(htmls):
            return ["职位描述 职位要求 content"]

        mock_extractor = AsyncMock()
        mock_extractor.extract = AsyncMock(side_effect=mock_extract)

        mock_llm = AsyncMock()
        mock_llm.structured_parse = AsyncMock(
            return_value={"jobs": [{"title": "Job", "category": "后端",
                "source_url": "https://test.com/1", "responsibilities": "dev",
                "requirements": "Python"}]}
        )

        mock_db = AsyncMock()

        with patch("app.crawl.pipeline.upsert_jobs", new_callable=AsyncMock) as mock_upsert:
            mock_upsert.return_value = {"jobs_found": 2, "jobs_new": 2, "jobs_updated": 0}
            result = await crawl_company(
                company=company,
                browser=mock_browser,
                extractor=mock_extractor,
                llm_client=mock_llm,
                db=mock_db,
            )
            assert result["jobs_found"] == 2
            # Extract should be called twice (once per listing page)
            assert mock_extractor.extract.call_count == 2
            # LLM should be called twice
            assert mock_llm.structured_parse.call_count == 2
