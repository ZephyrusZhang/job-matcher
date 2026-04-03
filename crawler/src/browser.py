import asyncio
import base64
import json
import re
import threading
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Response

from .traffic_utils import (
    filter_headers,
    has_struct_list,
    score_api,
    summarize_structure,
    truncate_response,
)

IGNORED_PATTERNS = [
    r"google-analytics", r"googletagmanager", r"doubleclick",
    r"facebook\.com/tr", r"hotjar", r"beacon", r"collect\?",
    r"log\?", r"track\?", r"\.(png|jpg|gif|css|woff2?|js)(\?|$)",
]


class BrowserManager:
    def __init__(self):
        self.pw = None
        self.browser = None
        self.page = None
        self.captured: list[dict] = []
        # 专属事件循环，Playwright 所有操作绑定在此
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    def _run(self, coro):
        """在专属事件循环上执行协程，阻塞等待结果"""
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    def open(self, url: str) -> dict:
        return self._run(self._open(url))

    def action(self, action: str, **kwargs) -> dict:
        return self._run(self._action(action, **kwargs))

    def screenshot(self, full_page: bool = False) -> str:
        return self._run(self._screenshot(full_page))

    def close(self):
        self._run(self._close())
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)

    # ── 异步实现 ──

    async def _open(self, url: str) -> dict:
        self.captured = []
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=False)
        ctx = await self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )
        self.page = await ctx.new_page()
        self.page.on("response", self._on_response)
        await self.page.goto(url, wait_until="networkidle", timeout=30000)
        return {
            "title": await self.page.title(),
            "url": self.page.url,
            "captured_count": len(self.captured),
        }

    async def _on_response(self, response: Response):
        req = response.request
        if response.status != 200:
            return
        if req.resource_type in {"image", "media", "font", "stylesheet", "document", "manifest"}:
            return
        url = req.url
        if any(re.search(p, url, re.I) for p in IGNORED_PATTERNS):
            return
        ct = response.headers.get("content-type", "")
        if "json" not in ct:
            return
        try:
            body_text = await response.text()
            if len(body_text) < 50:
                return
            body_json = json.loads(body_text)
        except Exception:
            return

        post_data = None
        try:
            raw = req.post_data
            if raw:
                try:
                    post_data = json.loads(raw)
                except Exception:
                    post_data = raw
        except Exception:
            pass

        parsed = urlparse(url)
        self.captured.append({
            "method": req.method,
            "url": url,
            "path": parsed.path,
            "query": parsed.query,
            "status": response.status,
            "request_headers": dict(req.headers),
            "request_body": post_data,
            "response_body_preview": truncate_response(body_json),
            "response_size": len(body_text),
        })

    async def _action(self, action: str, **kwargs) -> dict:
        before = len(self.captured)
        if action == "click":
            await self.page.click(kwargs["selector"], timeout=5000)
        elif action == "scroll":
            d = kwargs.get("distance", 800)
            await self.page.evaluate(f"window.scrollBy(0, {d})")
        elif action == "type":
            await self.page.fill(kwargs["selector"], kwargs["value"])
        elif action == "goto":
            await self.page.goto(kwargs["value"], wait_until="networkidle")
        await self.page.wait_for_timeout(2500)
        return {"new_requests": len(self.captured) - before, "total": len(self.captured)}

    async def _screenshot(self, full_page: bool = False) -> str:
        buf = await self.page.screenshot(full_page=full_page)
        return base64.b64encode(buf).decode()

    # ── 同步工具方法（纯内存操作，无需事件循环）──

    def get_traffic(self, min_score: int = 0) -> list[dict]:
        results = []
        for i, r in enumerate(self.captured):
            score = score_api(r)
            if score < min_score:
                continue
            results.append({
                "index": i, "method": r["method"],
                "path": r["path"][:80], "status": r["status"],
                "size": r["response_size"], "score": score,
                "has_struct_list": has_struct_list(r["response_body_preview"]),
            })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def inspect(self, index: int) -> dict:
        r = self.captured[index]
        preview = r["response_body_preview"]
        ps = json.dumps(preview, ensure_ascii=False)
        if len(ps) > 3000:
            preview = summarize_structure(preview)
        return {
            "method": r["method"], "url": r["url"],
            "request_headers": filter_headers(r["request_headers"]),
            "request_body": r.get("request_body"),
            "response_preview": preview,
            "response_size": r["response_size"],
        }

    async def _close(self):
        if self.browser:
            await self.browser.close()
        if self.pw:
            await self.pw.stop()
        self.browser = self.pw = self.page = None
