"""Tests for the listing page analysis agent."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestAnalyzeListingPrompt:
    def test_build_messages(self):
        from app.llm.prompts.analyze_listing import build_analyze_listing_messages

        snippet = "URL: https://example.com/jobs\n=== 重复出现的链接组 ==="
        messages = build_analyze_listing_messages(
            page_text="软件工程师 北京 全职",
            page_url="https://example.com/jobs",
            html_snippet=snippet,
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "JSON" in messages[0]["content"]
        assert "DOM" in messages[1]["content"]

    def test_prompt_contains_key_instructions(self):
        from app.llm.prompts.analyze_listing import build_analyze_listing_messages

        messages = build_analyze_listing_messages("text", "url", "report")
        system = messages[0]["content"]
        assert "job_card_selector" in system
        assert "card_strategy" in system
        assert "next_button_selector" in system
        assert "page_number_selector" in system
        assert "href" in system
        assert "click" in system
        assert "不要自己编造" in system


class TestListingAnalyzer:
    @pytest.fixture
    def llm_client(self):
        mock = AsyncMock()
        mock.structured_parse = AsyncMock()
        return mock

    async def test_analyze_returns_pattern(self, llm_client):
        from app.crawl.agent import ListingAnalyzer

        llm_client.structured_parse.return_value = {
            "job_links": ["https://example.com/job/1", "https://example.com/job/2"],
            "job_card_selector": "a.job-link",
            "card_strategy": "href",
            "next_button_selector": "a.next-btn",
            "page_number_selector": "li.page-num",
            "confidence": 0.95,
        }

        analyzer = ListingAnalyzer(llm_client)
        pattern = await analyzer.analyze_page("text", "https://example.com", "<html/>")

        assert pattern.job_card_selector == "a.job-link"
        assert pattern.card_strategy == "href"
        assert len(pattern.job_links) == 2
        assert pattern.next_button_selector == "a.next-btn"
        assert pattern.page_number_selector == "li.page-num"
        assert pattern.confidence == 0.95
        llm_client.structured_parse.assert_called_once()

    async def test_analyze_click_strategy(self, llm_client):
        from app.crawl.agent import ListingAnalyzer

        llm_client.structured_parse.return_value = {
            "job_links": [],
            "job_card_selector": "li.post_box",
            "card_strategy": "click",
            "next_button_selector": None,
            "page_number_selector": None,
            "confidence": 0.8,
        }

        analyzer = ListingAnalyzer(llm_client)
        pattern = await analyzer.analyze_page("text", "url", "html")

        assert pattern.card_strategy == "click"
        assert pattern.job_links == []

    async def test_analyze_handles_missing_fields(self, llm_client):
        """LLM returns incomplete JSON — should fill defaults."""
        from app.crawl.agent import ListingAnalyzer

        llm_client.structured_parse.return_value = {
            "job_card_selector": "div.card",
            "card_strategy": "click",
        }

        analyzer = ListingAnalyzer(llm_client)
        pattern = await analyzer.analyze_page("text", "url", "html")

        assert pattern.job_card_selector == "div.card"
        assert pattern.job_links == []
        assert pattern.next_button_selector is None
        assert pattern.confidence == 0.0

    async def test_analyze_raises_on_llm_error(self, llm_client):
        """LLM failure should propagate."""
        from app.crawl.agent import ListingAnalyzer

        llm_client.structured_parse.side_effect = RuntimeError("API error")

        analyzer = ListingAnalyzer(llm_client)
        with pytest.raises(RuntimeError):
            await analyzer.analyze_page("text", "url", "html")


class TestSimplifyHtml:
    def test_removes_script_style(self):
        from app.crawl.agent import simplify_html

        html = '<html><head><style>body{}</style></head><body><script>alert(1)</script><div class="job">Hello</div></body></html>'
        result = simplify_html(html)
        assert "<script>" not in result
        assert "<style>" not in result
        assert "job" in result

    def test_truncates_text_nodes(self):
        from app.crawl.agent import simplify_html

        html = '<div class="desc">' + "A" * 200 + "</div>"
        result = simplify_html(html)
        assert len(result) < len(html)

    def test_preserves_class_id_href(self):
        from app.crawl.agent import simplify_html

        html = '<a id="link1" class="job-card" href="/job/1" data-track="click">Job Title</a>'
        result = simplify_html(html)
        assert 'class="job-card"' in result
        assert 'href="/job/1"' in result
        assert 'id="link1"' in result

    def test_max_length(self):
        from app.crawl.agent import simplify_html

        html = "<body>" + '<div class="item">text</div>' * 500 + "</body>"
        result = simplify_html(html, max_length=2000)
        assert len(result) <= 2000

    def test_empty_html(self):
        from app.crawl.agent import simplify_html

        assert simplify_html("") == ""
