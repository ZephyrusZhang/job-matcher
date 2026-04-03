import json

from .browser import BrowserManager
from .sandbox import SandboxManager

# ── 工具定义（OpenAI function calling 格式）──

# 第一组：浏览器操控（本地，流量捕获分析用）
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "browser_open",
            "description": (
                "用 Playwright 打开目标 URL，开始拦截所有网络请求。"
                "只记录 status=200 的 JSON 响应，自动过滤静态资源和埋点。"
                "返回：页面标题、当前 URL、初始捕获请求数。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "目标网页 URL"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_action",
            "description": (
                "在当前页面执行操作以触发网络请求。"
                "支持：click（点击）、scroll（滚动）、type（输入）、goto（跳转）。"
                "返回：本次新增请求数、当前总请求数。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["click", "scroll", "type", "goto"]},
                    "selector": {"type": "string", "description": "CSS选择器（click/type时必填）"},
                    "value": {"type": "string", "description": "输入内容（type）或目标URL（goto）"},
                    "distance": {"type": "integer", "description": "滚动距离px（scroll时，默认800）"},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_screenshot",
            "description": "截取当前页面截图，返回 base64 图片。用于观察页面结构。",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_page": {"type": "boolean", "description": "是否截全页（默认false）"},
                },
            },
        },
    },
]

# 第二组：流量分析（本地，操作内存中的 captured 数据）
TOOLS += [
    {
        "type": "function",
        "function": {
            "name": "get_traffic",
            "description": (
                "获取已捕获的 JSON 接口摘要列表。"
                "每条包含：序号、method、path、status、大小、评分、是否含结构化列表。"
                "评分>=7 高置信度数据接口。此工具只返回摘要，详情用 inspect_request。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "min_score": {"type": "integer", "description": "最低评分过滤（默认0）"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_request",
            "description": (
                "查看某个请求的完整详情（截断版）：完整URL、请求头、请求体、响应体预览。"
                "响应体中的数组只保留前2条，长字符串已截断。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "request_index": {"type": "integer", "description": "请求序号（从 get_traffic 获取）"},
                },
                "required": ["request_index"],
            },
        },
    },
]

# 第三组：Docker 沙箱执行（云端，运行所有生成的代码）
TOOLS += [
    {
        "type": "function",
        "function": {
            "name": "sandbox_write_file",
            "description": "在 Docker 沙箱中写入文件。用于写入爬虫脚本。目录不存在会自动创建。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "沙箱内文件路径，如 /home/user/crawler.py"},
                    "content": {"type": "string", "description": "文件内容"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_run_command",
            "description": (
                "在 Docker 沙箱中执行 shell 命令。用于安装依赖、运行爬虫、查看输出。"
                "沙箱已预装 Python 3.11、pip。Playwright + Chromium 按需安装。"
                "返回：exit_code、stdout（最后5000字符）、stderr（最后3000字符）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令"},
                    "timeout": {"type": "integer", "description": "超时秒数（默认120）"},
                },
                "required": ["command"],
            },
        },
    },
]


# ── 工具执行路由 ──

browser_mgr = BrowserManager()
sandbox_mgr = SandboxManager()


def execute_tool(name: str, args: dict) -> str:
    match name:
        # 本地浏览器工具（流量捕获阶段）
        case "browser_open":
            return json.dumps(browser_mgr.open(args["url"]), ensure_ascii=False)
        case "browser_action":
            return json.dumps(browser_mgr.action(**args), ensure_ascii=False)
        case "browser_screenshot":
            return browser_mgr.screenshot(args.get("full_page", False))

        # 本地流量分析工具（操作内存中的 captured 数据）
        case "get_traffic":
            return json.dumps(browser_mgr.get_traffic(args.get("min_score", 0)), ensure_ascii=False)
        case "inspect_request":
            return json.dumps(browser_mgr.inspect(args["request_index"]), ensure_ascii=False)

        # Docker 沙箱工具（执行所有生成的爬虫代码）
        case "sandbox_write_file":
            return json.dumps(sandbox_mgr.write_file(args["path"], args["content"]), ensure_ascii=False)
        case "sandbox_run_command":
            return json.dumps(
                sandbox_mgr.run_command(args["command"], args.get("timeout", 120)),
                ensure_ascii=False,
            )

        case _:
            return json.dumps({"error": f"未知工具: {name}"})
