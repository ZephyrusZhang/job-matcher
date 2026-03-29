"""
分阶段测试爬虫管线的各个环节。
用法：
    # 阶段1：测试 Playwright 能否渲染目标页面
    uv run python scripts/test_crawl_stages.py browser "https://jobs.bytedance.com/campus/position" 2

    # 阶段2：测试 Crawl4AI 能否从 HTML 提取内容
    uv run python scripts/test_crawl_stages.py extract

    # 阶段3：测试 LLM 能否结构化解析
    uv run python scripts/test_crawl_stages.py parse 字节跳动

    # 完整流水线测试（爬取与解析并行）
    uv run python scripts/test_crawl_stages.py full "https://jobs.bytedance.com/campus/position" 字节跳动 2
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_browser(url: str, max_pages: int = 1):
    """阶段1：验证 Playwright 渲染（逐页 yield）"""
    from app.config import CrawlConfig
    from app.crawl.browser import BrowserManager

    print(f"\n{'='*60}")
    print(f"[阶段1] Playwright 渲染测试")
    print(f"目标 URL: {url}")
    print(f"最大页数: {max_pages}")
    print(f"{'='*60}\n")

    config = CrawlConfig(browser_headless=False)
    browser = BrowserManager(config)

    all_pages = []
    try:
        await browser.init()
        print("✓ 浏览器启动成功\n")

        page_num = 0
        async for detail_htmls in browser.crawl_listing_pages(url, max_pages=max_pages):
            page_num += 1
            print(f"列表页 {page_num}: 收集到 {len(detail_htmls)} 个详情页")
            for i, html in enumerate(detail_htmls):
                size_kb = len(html) / 1024
                idx = len(all_pages) + i
                out = Path(f"/tmp/crawl_page_{idx}.html")
                out.write_text(html, encoding="utf-8")
                print(f"  详情 {idx}: {size_kb:.1f} KB → {out}")
            all_pages.extend(detail_htmls)

        print(f"\n✓ 共收集 {len(all_pages)} 个详情页，跨 {page_num} 个列表页")
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

    detail_texts = [t for t in texts if "职位描述" in t or "职位要求" in t]
    skipped = len(texts) - len(detail_texts)
    print(f"共 {len(texts)} 个文本块，过滤掉 {skipped} 个非详情页，剩余 {len(detail_texts)} 个\n")

    for i, text in enumerate(detail_texts):
        has_req = "职位要求" in text or "任职要求" in text
        print(f"  [页 {i+1}] {len(text)} 字符, 含职位要求: {'✓' if has_req else '✗'}")

    print(f"\n并行发送 {len(detail_texts)} 个 LLM 请求...\n")

    async def _parse_page(i, text):
        messages = build_parse_job_messages(text, company_name)
        try:
            result = await client.structured_parse(messages)
            jobs = result.get("jobs", [])
            for job in jobs:
                print(f"  [页 {i+1}] ✓ {job.get('title')}: requirements={('有' if job.get('requirements') else '无')}")
            return jobs
        except Exception as e:
            print(f"  [页 {i+1}] ✗ 解析失败: {e}")
            return []

    results = await asyncio.gather(*[_parse_page(i, t) for i, t in enumerate(detail_texts)])
    all_jobs = [job for page_jobs in results for job in page_jobs]

    print(f"\n✓ 共解析出 {len(all_jobs)} 个技术岗位\n")

    for i, job in enumerate(all_jobs[:10]):
        print(f"--- 岗位 {i+1} ---")
        print(f"  名称:     {job.get('title')}")
        print(f"  方向:     {job.get('category')}")
        print(f"  地点:     {job.get('location')}")
        print(f"  职责:     {(job.get('responsibilities') or '')[:80]}...")
        print(f"  要求:     {(job.get('requirements') or '')[:100]}...")
        print(f"  学历:     {job.get('education')}")
        print()

    out = Path("/tmp/crawl_parsed.json")
    out.write_text(json.dumps({"jobs": all_jobs}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ 完整解析结果已保存到 {out}")
    return all_jobs


async def test_full(url: str, company_name: str, max_pages: int = 1):
    """完整流水线测试：爬取与解析并行执行"""
    from app.config import CrawlConfig, load_config
    from app.crawl.browser import BrowserManager
    from app.crawl.extractor import ContentExtractor
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
    config = CrawlConfig(browser_headless=False)
    browser = BrowserManager(config)

    t0 = time.time()
    all_jobs = []
    pending_task: asyncio.Task | None = None
    total_details = 0
    page_num = 0

    async def _extract_and_parse(htmls: list[str], batch_label: str) -> list[dict]:
        """Extract text from HTMLs, filter, parse all in parallel."""
        texts = await extractor.extract(htmls)
        details = [t for t in texts if "职位描述" in t or "职位要求" in t]
        print(f"  [{batch_label}] 提取 {len(texts)} 文本块, {len(details)} 个是岗位详情")

        if not details:
            return []

        async def _parse_one(i, text):
            messages = build_parse_job_messages(text, company_name)
            try:
                result = await llm_client.structured_parse(messages)
                jobs = result.get("jobs", [])
                for job in jobs:
                    print(f"  [{batch_label}] ✓ {job.get('title')}")
                return jobs
            except Exception as e:
                print(f"  [{batch_label}] ✗ 解析失败: {e}")
                return []

        results = await asyncio.gather(*[_parse_one(i, t) for i, t in enumerate(details)])
        return [job for page_jobs in results for job in page_jobs]

    try:
        await browser.init()
        print("✓ 浏览器启动成功\n")

        async for detail_htmls in browser.crawl_listing_pages(url, max_pages=max_pages):
            page_num += 1
            print(f"📄 列表页 {page_num}: 收集到 {len(detail_htmls)} 个详情页")
            total_details += len(detail_htmls)

            # Collect previous batch's results (if any)
            if pending_task is not None:
                jobs = await pending_task
                all_jobs.extend(jobs)

            # Start extract+parse for this batch in background
            label = f"列表页{page_num}"
            pending_task = asyncio.create_task(
                _extract_and_parse(detail_htmls, label)
            )

        # Collect the last batch
        if pending_task is not None:
            jobs = await pending_task
            all_jobs.extend(jobs)

    finally:
        await browser.close()

    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print(f"✓ 流水线完成!")
    print(f"  列表页数:   {page_num}")
    print(f"  详情页数:   {total_details}")
    print(f"  解析岗位数: {len(all_jobs)}")
    print(f"  总耗时:     {elapsed:.1f}s")
    print(f"{'='*60}\n")

    for i, job in enumerate(all_jobs[:10]):
        print(f"--- 岗位 {i+1} ---")
        print(f"  名称: {job.get('title')}")
        print(f"  方向: {job.get('category')}")
        print(f"  地点: {job.get('location')}")
        print(f"  要求: {(job.get('requirements') or '')[:100]}...")
        print()

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
