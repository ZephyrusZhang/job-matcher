"""
Playwright 网络请求拦截器（两阶段，手动控制）
阶段1: 打开岗位列表页，捕获列表相关 API，按 Enter 进入下一阶段
阶段2: 自动点击第一个岗位卡片，捕获详情相关 API，按 Enter 结束

用法: python interceptor.py <url>
示例: python interceptor.py "https://careers.tencent.com/search.html"
"""

import asyncio
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright, Page, BrowserContext


# ---- 输出目录 ----
OUTPUT_DIR = Path("./generated")


# ---- 过滤规则 ----

SKIP_DOMAINS = {
    "mcs.zijieapi.com", "mcs-bd-my.larkoffice.com",
    "starling.zijieapi.com",
    "beacon.qq.com", "report.qq.com", "aegis.qq.com",
    "analytics.google.com", "www.google-analytics.com",
    "www.googletagmanager.com", "stats.g.doubleclick.net",
    "www.facebook.com", "connect.facebook.net",
    "hm.baidu.com", "tongji.baidu.com",
    "arms-retcode.aliyuncs.com",
    "sentry.io", "hotjar.com",
}

SKIP_PATH_KEYWORDS = [
    "/log", "/report", "/collect", "/pixel",
    "/monitor", "/webid", "/v1/list",
    "/check_and_get_text",
]

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot", ".map",
}


def should_skip(url_str: str) -> bool:
    parsed = urlparse(url_str)
    domain = parsed.hostname or ""
    if domain in SKIP_DOMAINS:
        return True
    path_lower = parsed.path.lower()
    if any(kw in path_lower for kw in SKIP_PATH_KEYWORDS):
        return True
    if any(path_lower.endswith(ext) for ext in SKIP_EXTENSIONS):
        return True
    return False


# ---- 请求捕获 ----

def make_response_handler(captured: list, phase: str):
    async def on_response(response):
        request = response.request
        if request.resource_type not in ("fetch", "xhr"):
            return
        url_str = request.url
        if should_skip(url_str):
            return

        entry = {
            "phase": phase,
            "url": url_str,
            "method": request.method,
            "request_headers": dict(request.headers),
            "post_data": None,
            "status": response.status,
            "response_headers": dict(response.headers),
            "response_body": None,
        }

        if request.method == "POST":
            try:
                entry["post_data"] = request.post_data
            except Exception:
                pass

        content_type = response.headers.get("content-type", "")
        if "json" in content_type or "text" in content_type:
            try:
                body = await response.text()
                try:
                    entry["response_body"] = json.loads(body)
                except json.JSONDecodeError:
                    entry["response_body"] = body[:2000]
            except Exception:
                entry["response_body"] = "<读取失败>"

        captured.append(entry)
        tag = "列表页" if phase == "list" else "详情页"
        print(f"  [{tag}] {request.method} {url_str[:120]}")

    return on_response


async def find_job_card(page: Page):
    selectors = [
        "a[href*='position']", "a[href*='job']", "a[href*='post_detail']",
        "a[href*='postid']", "a[href*='detail']",
        "[class*='job-card']", "[class*='position-card']", "[class*='post-card']",
        "[class*='job-item']", "[class*='position-item']", "[class*='post-item']",
        "[class*='jobCard']", "[class*='positionCard']", "[class*='postCard']",
        "[class*='jobItem']", "[class*='positionItem']", "[class*='postItem']",
        "[class*='recruit-list'] a[href]",
        "[class*='search-result'] a[href]",
        "[class*='list'] li a[href]",
    ]
    for selector in selectors:
        try:
            elements = await page.query_selector_all(selector)
            if elements:
                print(f"  找到岗位卡片: {selector} (共 {len(elements)} 个)")
                return elements[0]
        except Exception:
            continue
    return None


async def wait_for_enter(prompt_msg: str):
    """异步等待用户按 Enter"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: input(prompt_msg))


async def run(url: str, output_path: Path, scroll: bool):
    captured = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        # ========== 阶段1: 岗位列表页 ==========
        print(f"\n{'='*60}")
        print(f"【阶段1】打开岗位列表页")
        print(f"  URL: {url}")
        print(f"{'='*60}\n")

        list_handler = make_response_handler(captured, "list")
        page.on("response", list_handler)

        await page.goto(url, wait_until="networkidle", timeout=30000)

        if scroll:
            print("  自动滚动触发懒加载...")
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(1)

        list_count = len(captured)
        print(f"\n  ✓ 列表页已捕获 {list_count} 个请求")
        print(f"  你可以在浏览器中操作（翻页、筛选等），新请求会持续捕获")
        await wait_for_enter("\n  >>> 按 Enter 进入【阶段2: 详情页捕获】... ")

        list_count = len(captured)  # 更新（用户可能在等待期间触发了更多请求）
        print(f"\n  ✓ 列表页最终捕获 {list_count} 个请求\n")

        # ========== 阶段2: 岗位详情页 ==========
        print(f"{'='*60}")
        print(f"【阶段2】点击岗位卡片，捕获详情页请求")
        print(f"{'='*60}\n")

        page.remove_listener("response", list_handler)
        detail_handler = make_response_handler(captured, "detail")
        page.on("response", detail_handler)

        # 监听新标签页
        detail_page = None

        async def on_new_page(new_page: Page):
            nonlocal detail_page
            detail_page = new_page
            new_page.on("response", make_response_handler(captured, "detail"))
            print(f"  检测到新标签页: {new_page.url[:100]}")

        context.on("page", on_new_page)

        target = await find_job_card(page)
        if target:
            url_before = page.url
            pages_before = len(context.pages)

            print("  正在点击第一个岗位卡片...")
            await target.click()
            await asyncio.sleep(3)

            pages_after = len(context.pages)

            if pages_after > pages_before or detail_page:
                print("  → 场景A: 新标签页打开")
                if detail_page:
                    try:
                        await detail_page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    print(f"  详情页 URL: {detail_page.url[:120]}")
            elif page.url != url_before:
                print(f"  → 场景B: 同标签页跳转")
                print(f"  详情页 URL: {page.url[:120]}")
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
            else:
                print("  → 场景C: 同页面变化（侧边栏/弹窗）")
        else:
            print("  ⚠ 未自动找到岗位卡片，请在浏览器中手动点击一个岗位")

        detail_count = len(captured) - list_count
        print(f"\n  ✓ 详情页已捕获 {detail_count} 个请求")
        print(f"  你也可以手动点击其他岗位卡片，新请求会持续捕获")
        await wait_for_enter("\n  >>> 按 Enter 结束捕获并保存... ")

        detail_count = len(captured) - list_count
        print(f"\n  ✓ 详情页最终捕获 {detail_count} 个请求\n")

        await browser.close()

    # ---- 保存与摘要 ----
    print(f"{'='*60}")
    print(f"捕获汇总: 列表页 {list_count} 个 + 详情页 {detail_count} 个 = 共 {len(captured)} 个")
    print(f"{'='*60}\n")

    for i, entry in enumerate(captured):
        tag = "列表" if entry["phase"] == "list" else "详情"
        body_preview = ""
        if isinstance(entry["response_body"], dict):
            body_preview = f"keys: {list(entry['response_body'].keys())[:5]}"
        elif isinstance(entry["response_body"], str):
            body_preview = entry["response_body"][:60]
        print(f"  [{i+1}][{tag}] {entry['method']} {entry['url'][:100]}")
        print(f"         Status: {entry['status']} | {body_preview}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(captured, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="两阶段拦截：列表页 + 详情页（按 Enter 切换阶段）")
    parser.add_argument("url", help="岗位列表页 URL")
    parser.add_argument("--output", default=None, help="输出文件路径（默认 ./generated/captured_requests.json）")
    parser.add_argument("--scroll", action="store_true", help="自动滚动列表页")
    args = parser.parse_args()

    output = Path(args.output) if args.output else OUTPUT_DIR / "captured_requests.json"
    asyncio.run(run(args.url, output, args.scroll))


if __name__ == "__main__":
    main()