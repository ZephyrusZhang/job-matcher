"""LangChain tool wrappers for the crawl agent.

These wrap the exact same ``browser_mgr`` / ``sandbox_mgr`` calls that
``app/crawl/tools.py::execute_tool`` routes to, keeping tool names, descriptions,
parameter schemas and return payloads byte-for-byte identical so the agent's
behaviour does not change with the move to LangGraph.

The managers are synchronous and block (Playwright driving a real browser,
Docker exec against a sandbox container), so every tool hops to a worker thread
via ``asyncio.to_thread``. That keeps the agent runnable on the application's
main event loop, which the shared Postgres checkpointer pool requires.
"""

import asyncio
import json
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import (
    BaseModel,
    Field,
)

from app.crawl.tools import (
    browser_mgr,
    sandbox_mgr,
)

# Matches the truncation the previous ReAct loop applied to every tool result
# before appending it to the message history.
MAX_TOOL_RESULT_CHARS = 12000


def truncate_tool_result(result: str, max_chars: int = MAX_TOOL_RESULT_CHARS) -> str:
    """Truncate an oversized tool result, keeping the head and tail."""
    if len(result) <= max_chars:
        return result
    head = max_chars * 2 // 3
    tail = max_chars // 3
    return result[:head] + f"\n\n[...已截断，原始 {len(result)} 字符...]\n\n" + result[-tail:]


def _dumps(payload) -> str:
    """Serialize a tool payload the way the original loop did."""
    return truncate_tool_result(json.dumps(payload, ensure_ascii=False))


# ── 第一组：浏览器操控（本地，流量捕获分析用）──


class BrowserOpenArgs(BaseModel):
    """Arguments for ``browser_open``."""

    url: str = Field(description="目标网页 URL")


async def _browser_open(url: str) -> str:
    return _dumps(await asyncio.to_thread(browser_mgr.open, url))


browser_open = StructuredTool.from_function(
    coroutine=_browser_open,
    name="browser_open",
    description=(
        "用 Playwright 打开目标 URL，开始拦截所有网络请求。"
        "只记录 status=200 的 JSON 响应，自动过滤静态资源和埋点。"
        "返回：页面标题、当前 URL、初始捕获请求数。"
    ),
    args_schema=BrowserOpenArgs,
)


class BrowserActionArgs(BaseModel):
    """Arguments for ``browser_action``."""

    action: str = Field(description="click / scroll / type / goto")
    selector: Optional[str] = Field(default=None, description="CSS选择器（click/type时必填）")
    value: Optional[str] = Field(default=None, description="输入内容（type）或目标URL（goto）")
    distance: Optional[int] = Field(default=None, description="滚动距离px（scroll时，默认800）")


async def _browser_action(
    action: str,
    selector: Optional[str] = None,
    value: Optional[str] = None,
    distance: Optional[int] = None,
) -> str:
    # Only forward supplied arguments, matching the original ``**args`` call so
    # the manager's own defaults still apply.
    kwargs = {k: v for k, v in (("selector", selector), ("value", value), ("distance", distance)) if v is not None}
    return _dumps(await asyncio.to_thread(lambda: browser_mgr.action(action, **kwargs)))


browser_action = StructuredTool.from_function(
    coroutine=_browser_action,
    name="browser_action",
    description=(
        "在当前页面执行操作以触发网络请求。"
        "支持：click（点击）、scroll（滚动）、type（输入）、goto（跳转）。"
        "返回：本次新增请求数、当前总请求数。"
    ),
    args_schema=BrowserActionArgs,
)


class BrowserScreenshotArgs(BaseModel):
    """Arguments for ``browser_screenshot``."""

    full_page: bool = Field(default=False, description="是否截全页（默认false）")


async def _browser_screenshot(full_page: bool = False) -> str:
    # Returns a raw base64 string, not JSON — same as the original tool.
    return truncate_tool_result(await asyncio.to_thread(browser_mgr.screenshot, full_page))


browser_screenshot = StructuredTool.from_function(
    coroutine=_browser_screenshot,
    name="browser_screenshot",
    description="截取当前页面截图，返回 base64 图片。用于观察页面结构。",
    args_schema=BrowserScreenshotArgs,
)


# ── 第二组：流量分析（本地，操作内存中的 captured 数据）──


class GetTrafficArgs(BaseModel):
    """Arguments for ``get_traffic``."""

    min_score: int = Field(default=0, description="最低评分过滤（默认0）")


async def _get_traffic(min_score: int = 0) -> str:
    return _dumps(await asyncio.to_thread(browser_mgr.get_traffic, min_score))


get_traffic = StructuredTool.from_function(
    coroutine=_get_traffic,
    name="get_traffic",
    description=(
        "获取已捕获的 JSON 接口摘要列表。"
        "每条包含：序号、method、path、status、大小、评分、是否含结构化列表。"
        "评分>=7 高置信度数据接口。此工具只返回摘要，详情用 inspect_request。"
    ),
    args_schema=GetTrafficArgs,
)


class InspectRequestArgs(BaseModel):
    """Arguments for ``inspect_request``."""

    request_index: int = Field(description="请求序号（从 get_traffic 获取）")


async def _inspect_request(request_index: int) -> str:
    return _dumps(await asyncio.to_thread(browser_mgr.inspect, request_index))


inspect_request = StructuredTool.from_function(
    coroutine=_inspect_request,
    name="inspect_request",
    description=(
        "查看某个请求的完整详情（截断版）：完整URL、请求头、请求体、响应体预览。"
        "响应体中的数组只保留前2条，长字符串已截断。"
    ),
    args_schema=InspectRequestArgs,
)


# ── 第三组：流量搜索（本地，按关键词搜索捕获的请求和响应）──


class SearchTrafficArgs(BaseModel):
    """Arguments for ``search_traffic``."""

    keyword: str = Field(description="搜索关键词（不区分大小写）")


async def _search_traffic(keyword: str) -> str:
    return _dumps(await asyncio.to_thread(browser_mgr.search_traffic, keyword))


search_traffic = StructuredTool.from_function(
    coroutine=_search_traffic,
    name="search_traffic",
    description=(
        "按关键词搜索所有已捕获的请求。搜索范围包括 URL、请求体和响应体。"
        "用于发现特定接口，例如搜索 'category' 可找到类别映射接口，"
        "搜索 'dict' 或 'enum' 可找到枚举/字典数据接口。"
        "返回匹配的请求摘要列表（序号、URL、匹配位置）。"
    ),
    args_schema=SearchTrafficArgs,
)


# ── 第四组：Docker 沙箱执行（云端，运行所有生成的代码）──


class SandboxWriteFileArgs(BaseModel):
    """Arguments for ``sandbox_write_file``."""

    path: str = Field(description="沙箱内文件路径，如 /home/user/crawler.py")
    content: str = Field(description="文件内容")


async def _sandbox_write_file(path: str, content: str) -> str:
    return _dumps(await asyncio.to_thread(sandbox_mgr.write_file, path, content))


sandbox_write_file = StructuredTool.from_function(
    coroutine=_sandbox_write_file,
    name="sandbox_write_file",
    description="在 Docker 沙箱中写入文件。用于写入爬虫脚本。目录不存在会自动创建。",
    args_schema=SandboxWriteFileArgs,
)


class SandboxRunCommandArgs(BaseModel):
    """Arguments for ``sandbox_run_command``."""

    command: str = Field(description="要执行的命令")
    timeout: int = Field(default=120, description="超时秒数（默认120）")


async def _sandbox_run_command(command: str, timeout: int = 120) -> str:
    return _dumps(await asyncio.to_thread(sandbox_mgr.run_command, command, timeout))


sandbox_run_command = StructuredTool.from_function(
    coroutine=_sandbox_run_command,
    name="sandbox_run_command",
    description=(
        "在 Docker 沙箱中执行 shell 命令。用于安装依赖、运行爬虫、查看输出。"
        "沙箱已预装 Python 3.11、pip。Playwright + Chromium 按需安装。"
        "返回：exit_code、stdout（最后5000字符）、stderr（最后3000字符）。"
    ),
    args_schema=SandboxRunCommandArgs,
)


# Order matches the original TOOLS list in app/crawl/tools.py.
CRAWL_TOOLS = [
    browser_open,
    browser_action,
    browser_screenshot,
    get_traffic,
    inspect_request,
    search_traffic,
    sandbox_write_file,
    sandbox_run_command,
]
