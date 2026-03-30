"""
分阶段测试爬虫管线的各个环节。
用法：
    # 阶段1：测试 Playwright 渲染 + Agent 分析
    uv run python scripts/test_crawl_stages.py browser "https://jobs.bytedance.com/campus/position" 2

    # 阶段2：测试 Crawl4AI 内容提取
    uv run python scripts/test_crawl_stages.py extract

    # 阶段3：测试 LLM 结构化解析
    uv run python scripts/test_crawl_stages.py parse 字节跳动

    # 完整流水线测试（Agent 驱动 + 爬取与解析并行）
    uv run python scripts/test_crawl_stages.py full "https://jobs.bytedance.com/campus/position" 字节跳动 2
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_browser(url: str, max_pages: int = 1):
    """阶段1：验证 Playwright 渲染 + Agent 页面分析"""
    from app.config import CrawlConfig, load_config
    from app.crawl.browser import BrowserManager
    from app.crawl.agent import ListingAnalyzer
    from app.crawl.selector_cache import SelectorCache
    from app.llm.client import LLMClient

    print(f"\n{'='*60}")
    print(f"[阶段1] Playwright + Agent 渲染测试")
    print(f"目标 URL: {url}")
    print(f"最大页数: {max_pages}")
    print(f"{'='*60}\n")

    app_config = load_config()
    llm_client = LLMClient(app_config.llm)
    analyzer = ListingAnalyzer(llm_client)
    cache = SelectorCache(lock_threshold=app_config.crawl.agent_lock_threshold)

    config = CrawlConfig(browser_headless=False)
    browser = BrowserManager(config)

    all_pages = []
    try:
        await browser.init()
        print("✓ 浏览器启动成功\n")

        page = await browser.open_page(url)
        pages_crawled = 0

        while True:
            pages_crawled += 1
            print(f"{'─'*40}")
            print(f"📄 列表页 {pages_crawled}")

            await browser.scroll_to_bottom(page)

            detail_htmls = []
            if cache.is_locked():
                locked = cache.get_locked()
                print(f"  🔒 使用锁定选择器: {locked.job_card_selector} ({locked.card_strategy})")
                detail_htmls = await browser.collect_details_by_selector(
                    page, locked.job_card_selector, locked.card_strategy
                )
            else:
                print(f"  🤖 Agent 分析页面...")
                ctx = await browser.get_page_context(page)
                pattern = await analyzer.analyze_page(ctx.text, ctx.url, ctx.html_snippet)
                cache.record(pattern)
                print(f"  → selector: {pattern.job_card_selector}")
                print(f"  → strategy: {pattern.card_strategy}")
                print(f"  → links: {len(pattern.job_links)}")
                print(f"  → next_btn:  {pattern.next_button_selector}")
                print(f"  → page_num:  {pattern.page_number_selector}")
                print(f"  → confidence: {pattern.confidence:.2f}")
                print(f"  → locked: {cache.is_locked()}")

                if pattern.job_links:
                    detail_htmls = await browser.collect_details_by_links(page, pattern.job_links)
                elif pattern.job_card_selector:
                    detail_htmls = await browser.collect_details_by_selector(
                        page, pattern.job_card_selector, pattern.card_strategy
                    )

            print(f"  ✓ 收集到 {len(detail_htmls)} 个详情页")

            for i, html in enumerate(detail_htmls):
                idx = len(all_pages) + i
                out = Path(f"/tmp/crawl_page_{idx}.html")
                out.write_text(html, encoding="utf-8")
            all_pages.extend(detail_htmls)

            if max_pages != -1 and pages_crawled >= max_pages:
                break

            await browser.close_other_tabs(page)
            await browser.scroll_to_bottom(page)

            next_btn = None
            page_num_sel = None
            if cache.is_locked():
                lk = cache.get_locked()
                next_btn = lk.next_button_selector
                page_num_sel = lk.page_number_selector
            elif pattern:
                next_btn = pattern.next_button_selector
                page_num_sel = pattern.page_number_selector
            if not await browser.go_next_page(page, pages_crawled, next_button_selector=next_btn, page_number_selector=page_num_sel):
                print(f"  ✗ 没有下一页")
                break
            # Wait for cards to render after pagination
            if cache.is_locked() and cache.get_locked().job_card_selector:
                await browser.wait_for_selector(page, cache.get_locked().job_card_selector)
            elif pattern and pattern.job_card_selector:
                await browser.wait_for_selector(page, pattern.job_card_selector)

        await browser.close_page(page)
        print(f"\n✓ 共收集 {len(all_pages)} 个详情页，跨 {pages_crawled} 个列表页")
        return all_pages
    except Exception as e:
        print(f"\n✗ 失败: {e}")
        raise
    finally:
        await browser.close()


async def test_extract(html_pages: list[str] | None = None):
    """阶段2：验证 Crawl4AI 内容提取"""
    from app.crawl.extractor import ContentExtractor

    print(f"\n{'='*60}")
    print(f"[阶段2] Crawl4AI 内容提取测试")
    print(f"{'='*60}\n")

    if html_pages is None:
        html_pages = []
        for p in sorted(Path("/tmp").glob("crawl_page_*.html")):
            html_pages.append(p.read_text(encoding="utf-8"))
        if not html_pages:
            print("✗ 未找到 /tmp/crawl_page_*.html，请先运行 browser 阶段")
            return None

    print(f"输入: {len(html_pages)} 个 HTML 页面")

    extractor = ContentExtractor()
    texts = await extractor.extract(html_pages)

    print(f"✓ 提取到 {len(texts)} 个文本块\n")
    for i, text in enumerate(texts[:3]):
        print(f"--- 文本块 {i+1} (前 500 字) ---")
        print(text[:500])
        print("...\n")

    out = Path("/tmp/crawl_extracted.json")
    out.write_text(json.dumps(texts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ 完整提取结果已保存到 {out}")
    return texts


async def test_parse(texts: list[str] | None = None, company_name: str = "测试公司"):
    """阶段3：验证 LLM 结构化解析"""
    from app.config import load_config
    from app.llm.client import LLMClient
    from app.llm.prompts.parse_job import build_parse_job_messages

    print(f"\n{'='*60}")
    print(f"[阶段3] LLM 结构化解析测试")
    print(f"{'='*60}\n")

    if texts is None:
        cached = Path("/tmp/crawl_extracted.json")
        if cached.exists():
            texts = json.loads(cached.read_text(encoding="utf-8"))
        else:
            print("✗ 未找到 /tmp/crawl_extracted.json，请先运行 extract 阶段")
            return None

    app_config = load_config()
    config = app_config.llm
    print(f"LLM 地址: {config.base_url}")
    print(f"解析模型: {config.model}\n")
    client = LLMClient(config)

    detail_texts = [t for t in texts if len(t.strip()) > 50]
    print(f"共 {len(texts)} 个文本块，{len(detail_texts)} 个非空\n")

    print(f"并行发送 {len(detail_texts)} 个 LLM 请求...\n")

    async def _parse_page(i, text):
        messages = build_parse_job_messages(text, company_name)
        try:
            result = await client.structured_parse(messages)
            jobs = result.get("jobs", [])
            for job in jobs:
                print(f"  [页 {i+1}] ✓ {job.get('title')}")
            return jobs
        except Exception as e:
            print(f"  [页 {i+1}] ✗ 解析失败: {e}")
            return []

    results = await asyncio.gather(*[_parse_page(i, t) for i, t in enumerate(detail_texts)])
    all_jobs = [job for page_jobs in results for job in page_jobs]

    print(f"\n✓ 共解析出 {len(all_jobs)} 个技术岗位\n")

    for i, job in enumerate(all_jobs):
        print(f"  {i+1}. [{job.get('category')}] {job.get('title')} — {job.get('location')}")

    out = Path("/tmp/crawl_parsed.json")
    out.write_text(json.dumps({"jobs": all_jobs}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ 完整解析结果已保存到 {out}")
    return all_jobs


async def test_full(url: str, company_name: str, max_pages: int = 1):
    """完整流水线测试：Agent 驱动 + 爬取与解析并行"""
    from app.config import CrawlConfig, load_config
    from app.crawl.browser import BrowserManager
    from app.crawl.extractor import ContentExtractor
    from app.crawl.agent import ListingAnalyzer
    from app.crawl.selector_cache import SelectorCache
    from app.llm.client import LLMClient
    from app.llm.prompts.parse_job import build_parse_job_messages

    print(f"\n{'='*60}")
    print(f"[完整流水线] {company_name}")
    print(f"目标 URL: {url}")
    print(f"最大页数: {max_pages}")
    print(f"{'='*60}\n")

    app_config = load_config()
    llm_client = LLMClient(app_config.llm)
    extractor = ContentExtractor()
    analyzer = ListingAnalyzer(llm_client)
    cache = SelectorCache(lock_threshold=app_config.crawl.agent_lock_threshold)

    config = CrawlConfig(browser_headless=False)
    browser = BrowserManager(config)

    t0 = time.time()
    all_jobs = []
    pending_task: asyncio.Task | None = None
    total_details = 0
    pages_crawled = 0

    async def _extract_and_parse(detail_pages: list[tuple[str, str]], label: str) -> list[dict]:
        """detail_pages: list of (html, source_url) tuples."""
        htmls = [html for html, _url in detail_pages]
        urls = [url for _html, url in detail_pages]

        texts = await extractor.extract(htmls)
        paired = [(t, u) for t, u in zip(texts, urls) if len(t.strip()) > 50]
        print(f"  [{label}] 提取 {len(texts)} 文本块, {len(paired)} 个非空")
        if not paired:
            return []

        async def _parse_one(i, text, source_url):
            messages = build_parse_job_messages(text, company_name)
            try:
                result = await llm_client.structured_parse(messages)
                jobs = result.get("jobs", [])
                for job in jobs:
                    job["source_url"] = source_url
                    print(f"  [{label}] ✓ {job.get('title')}")
                return jobs
            except Exception as e:
                print(f"  [{label}] ✗ 解析失败: {e}")
                return []

        results = await asyncio.gather(*[_parse_one(i, t, u) for i, (t, u) in enumerate(paired)])
        return [job for page_jobs in results for job in page_jobs]

    try:
        await browser.init()
        print("✓ 浏览器启动成功\n")

        page = await browser.open_page(url)
        pattern = None

        while True:
            pages_crawled += 1
            print(f"{'─'*40}")
            print(f"📄 列表页 {pages_crawled}")

            await browser.scroll_to_bottom(page)

            detail_htmls = []
            if cache.is_locked():
                locked = cache.get_locked()
                print(f"  🔒 锁定模式: {locked.job_card_selector} ({locked.card_strategy})")
                # 验证选择器能选中几个元素
                count = await page.evaluate(f"document.querySelectorAll('{locked.job_card_selector}').length")
                print(f"  📊 选择器匹配到 {count} 个元素")
                detail_htmls = await browser.collect_details_by_selector(
                    page, locked.job_card_selector, locked.card_strategy
                )
            else:
                print(f"  🤖 Agent 分析中...")
                ctx = await browser.get_page_context(page)
                # 保存 DOM 分析报告供检查
                Path("/tmp/crawl_dom_analysis.txt").write_text(ctx.html_snippet, encoding="utf-8")
                print(f"  📋 DOM 分析报告已保存到 /tmp/crawl_dom_analysis.txt")

                pattern = await analyzer.analyze_page(ctx.text, ctx.url, ctx.html_snippet)
                cache.record(pattern)
                print(f"  → selector:  {pattern.job_card_selector}")
                print(f"  → strategy:  {pattern.card_strategy}")
                print(f"  → links:     {len(pattern.job_links)} 个")
                if pattern.job_links:
                    for link in pattern.job_links[:5]:
                        print(f"      {link}")
                print(f"  → next_btn:  {pattern.next_button_selector}")
                print(f"  → page_num:  {pattern.page_number_selector}")
                print(f"  → confidence:{pattern.confidence:.2f}")
                print(f"  → locked:    {cache.is_locked()}")

                # 验证 Agent 返回的选择器
                if pattern.job_card_selector:
                    try:
                        count = await page.evaluate(
                            f"document.querySelectorAll('{pattern.job_card_selector}').length"
                        )
                        print(f"  📊 选择器 '{pattern.job_card_selector}' 匹配到 {count} 个元素")
                    except Exception as e:
                        print(f"  ⚠️ 选择器无效: {e}")

                if pattern.job_links:
                    print(f"  ➡️ 使用链接列表收集详情...")
                    detail_htmls = await browser.collect_details_by_links(page, pattern.job_links)
                elif pattern.job_card_selector:
                    print(f"  ➡️ 使用选择器 ({pattern.card_strategy}) 收集详情...")
                    detail_htmls = await browser.collect_details_by_selector(
                        page, pattern.job_card_selector, pattern.card_strategy
                    )
                else:
                    print(f"  ⚠️ Agent 未返回有效选择器")

            # detail_htmls is now list[tuple[str, str]] — (html, url)
            print(f"  ✓ 收集到 {len(detail_htmls)} 个详情页")
            if detail_htmls:
                for i, (html, durl) in enumerate(detail_htmls[:3]):
                    print(f"    详情 {i}: {len(html)} bytes — {durl[:80]}")
            total_details += len(detail_htmls)

            # Pipeline: collect previous + start new
            if pending_task is not None:
                jobs = await pending_task
                all_jobs.extend(jobs)

            if detail_htmls:
                pending_task = asyncio.create_task(
                    _extract_and_parse(detail_htmls, f"列表页{pages_crawled}")
                )
            else:
                pending_task = None

            if max_pages != -1 and pages_crawled >= max_pages:
                break

            await browser.close_other_tabs(page)
            await browser.scroll_to_bottom(page)

            next_btn = None
            page_num_sel = None
            if cache.is_locked():
                lk2 = cache.get_locked()
                next_btn = lk2.next_button_selector
                page_num_sel = lk2.page_number_selector
            elif pattern:
                next_btn = pattern.next_button_selector
                page_num_sel = pattern.page_number_selector

            if not await browser.go_next_page(page, pages_crawled, next_button_selector=next_btn, page_number_selector=page_num_sel):
                print(f"  ✗ 没有下一页")
                break
            # Wait for cards to render after pagination
            if cache.is_locked() and cache.get_locked().job_card_selector:
                await browser.wait_for_selector(page, cache.get_locked().job_card_selector)
            elif pattern and pattern.job_card_selector:
                await browser.wait_for_selector(page, pattern.job_card_selector)

        if pending_task is not None:
            jobs = await pending_task
            all_jobs.extend(jobs)

        await browser.close_page(page)

    finally:
        await browser.close()

    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print(f"✓ 流水线完成!")
    print(f"  列表页数:   {pages_crawled}")
    print(f"  详情页数:   {total_details}")
    print(f"  解析岗位数: {len(all_jobs)}")
    print(f"  总耗时:     {elapsed:.1f}s")
    print(f"{'='*60}\n")

    for i, job in enumerate(all_jobs):
        print(f"  {i+1}. [{job.get('category')}] {job.get('title')} — {job.get('location')}")

    out = Path("/tmp/crawl_parsed.json")
    out.write_text(json.dumps({"jobs": all_jobs}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ 完整结果已保存到 {out}")
    return all_jobs


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    stage = sys.argv[1]

    if stage == "browser":
        url = sys.argv[2] if len(sys.argv) > 2 else "https://jobs.bytedance.com/campus/position"
        max_p = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        asyncio.run(test_browser(url, max_pages=max_p))

    elif stage == "extract":
        asyncio.run(test_extract())

    elif stage == "parse":
        company = sys.argv[2] if len(sys.argv) > 2 else "测试公司"
        asyncio.run(test_parse(company_name=company))

    elif stage == "full":
        url = sys.argv[2] if len(sys.argv) > 2 else "https://jobs.bytedance.com/campus/position"
        company = sys.argv[3] if len(sys.argv) > 3 else "字节跳动"
        max_p = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        asyncio.run(test_full(url, company, max_pages=max_p))

    else:
        print(f"未知阶段: {stage}")
        print("可用阶段: browser, extract, parse, full")
        sys.exit(1)


if __name__ == "__main__":
    main()
