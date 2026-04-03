# 招聘爬虫 ReAct Agent —— 系统设计文档 v3

---

## 一、项目概述

### 目标
构建一个 ReAct 模式的 Agent，自动分析招聘网站的网络请求，生成爬虫代码并在沙箱中运行，最终输出结构化的岗位数据。

### 技术栈

| 组件 | 选型 | 说明 |
|------|------|------|
| 包管理 | **uv** | 替代 pip/poetry，速度快，lockfile 可复现 |
| LLM | **OpenAI SDK** → DeepSeek API | 兼容 OpenAI 接口，可无缝切换本地模型 |
| 浏览器自动化 | **Playwright** | 本地流量捕获分析 |
| 代码沙箱 | **E2B Sandbox** (Python SDK v1.3.x) | 执行所有生成的爬虫代码（httpx 和 Playwright） |
| Agent 框架 | **自建 ReAct Loop** | 基于 OpenAI SDK tool_calls，无额外框架依赖 |
| 可观测性 | **事件钩子** + Rich 终端 | 开发调试用终端输出 + JSONL 文件日志，可扩展接 Langfuse |

### 架构分工

```
┌─────────────────────────────────────────────────────────────┐
│                        Agent 主循环                          │
│                    （本地 Python 进程）                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │  LLM 调用     │    │  本地浏览器    │    │  E2B 沙箱     │   │
│  │  (DeepSeek)   │    │  (Playwright)  │    │  (云端隔离)   │   │
│  │              │    │              │    │              │   │
│  │  OpenAI SDK  │    │  流量捕获     │    │  执行所有生成  │   │
│  │  tool_calls  │    │  页面截图     │    │  的爬虫代码   │   │
│  │  兼容本地模型 │    │  页面交互     │    │  （含Playwright│   │
│  │              │    │              │    │   反爬方案）   │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

- **本地浏览器**：Agent 分析阶段使用，捕获目标网站的网络流量、截图、交互
- **E2B 沙箱**：所有 Agent 生成的爬虫代码都在 E2B 中执行，包括 httpx 方案和 Playwright 反爬方案

### 项目初始化

```bash
# 初始化项目
uv init crawler-agent
cd crawler-agent

# 添加核心依赖
uv add openai playwright e2b

# 安装本地 Playwright 浏览器（用于流量捕获）
uv run playwright install chromium
```

### 环境变量

```bash
# .env

# LLM 配置（DeepSeek）
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat

# 切换到本地模型时只需改这两行：
# LLM_BASE_URL=http://localhost:11434/v1    # Ollama
# LLM_MODEL=deepseek-v3:latest

# E2B 沙箱
E2B_API_KEY=e2b_xxx
```

---

## 二、LLM 调用层

### 2.1 使用 OpenAI SDK 调用 DeepSeek

DeepSeek API 完全兼容 OpenAI 接口格式，使用 `openai` Python SDK 即可调用。切换本地模型（Ollama、vLLM 等）只需修改 `base_url`。

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
)

MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
```

### 2.2 工具定义格式（OpenAI function calling）

DeepSeek 使用与 OpenAI 相同的 function calling 格式：

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "browser_open",
            "description": "...",
            "parameters": {
                "type": "object",
                "properties": { ... },
                "required": [...]
            }
        }
    },
    # ...
]
```

### 2.3 Tool Call 响应处理

```python
response = client.chat.completions.create(
    model=MODEL,
    messages=messages,
    tools=tools,
)
message = response.choices[0].message

# 检查是否有工具调用
if message.tool_calls:
    for tool_call in message.tool_calls:
        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)
        result = execute_tool(name, args)

        # 工具结果以 role="tool" 返回
        messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})
else:
    # 无工具调用 → 最终回复
    print(message.content)
```

### 2.4 本地模型兼容说明

| 提供商 | base_url | model | 备注 |
|--------|----------|-------|------|
| DeepSeek 官方 | `https://api.deepseek.com` | `deepseek-chat` | 推荐，tool calling 稳定 |
| Ollama | `http://localhost:11434/v1` | `deepseek-v3:latest` | 需确认模型支持 function calling |
| vLLM | `http://localhost:8000/v1` | 自定义 | 需启用 `--enable-auto-tool-choice` |
| OpenRouter | `https://openrouter.ai/api/v1` | `deepseek/deepseek-chat` | 多模型代理 |

---

## 三、流量数据清洗策略

### 3.1 拦截阶段过滤（capture 层）

在 Playwright 的 `page.on("response")` 回调中，第一道过滤：

```python
# 1. 只保留成功的 JSON 响应
if response.status != 200:
    return
content_type = response.headers.get("content-type", "")
if "json" not in content_type:
    return

# 2. 跳过静态资源、埋点、广告
IGNORED_PATTERNS = [
    r"google-analytics", r"doubleclick", r"hotjar",
    r"beacon", r"collect\?", r"log\?", r"track\?",
    r"\.(png|jpg|gif|css|woff|js)(\?|$)",
]
if any(re.search(p, url, re.I) for p in IGNORED_PATTERNS):
    return

# 3. 跳过过小的响应（通常是空结果或确认响应）
body = await response.text()
if len(body) < 50:
    return
```

### 3.2 响应体截断（存储层）

捕获的 JSON 响应在存入 `captured` 列表前，对响应体做结构化截断：

```python
def truncate_response(obj, max_array_items=2, max_str_len=200, max_depth=4, _depth=0):
    """
    截断策略：
    - 对象数组：只保留前 2 项 + 总数标注（结构相似，2 项足够 LLM 理解 schema）
    - 长字符串：截断到 200 字符 + 总长度标注
    - 嵌套深度 > 4 层：用类型摘要替代
    - 原始类型（数字、布尔、null）：原样保留
    """
    if _depth > max_depth:
        if isinstance(obj, dict):
            return f"{{...{len(obj)} fields}}"
        if isinstance(obj, list):
            return f"[...{len(obj)} items]"
        return obj

    if isinstance(obj, list):
        total = len(obj)
        is_struct_array = total > 0 and isinstance(obj[0], dict) and len(obj[0]) >= 3
        keep = max_array_items if is_struct_array else min(total, 5)
        truncated = [
            truncate_response(item, max_array_items, max_str_len, max_depth, _depth + 1)
            for item in obj[:keep]
        ]
        if total > keep:
            truncated.append(f"... 共 {total} 条，已省略 {total - keep} 条")
        return truncated

    if isinstance(obj, dict):
        return {
            k: truncate_response(v, max_array_items, max_str_len, max_depth, _depth + 1)
            for k, v in obj.items()
        }

    if isinstance(obj, str) and len(obj) > max_str_len:
        return obj[:max_str_len] + f"...({len(obj)}字符)"

    return obj
```

### 3.3 请求头精简

```python
USEFUL_HEADERS = {
    "content-type", "accept", "authorization", "cookie",
    "referer", "origin", "user-agent",
    "x-csrf-token", "x-requested-with", "x-bogus", "x-s",
}

def filter_headers(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if k.lower() in USEFUL_HEADERS}
```

### 3.4 get_traffic 只返回摘要

```python
def get_traffic_summary(captured, min_score=0):
    results = []
    for i, record in enumerate(captured):
        score = score_api(record)
        if score < min_score:
            continue
        results.append({
            "index": i,
            "method": record["method"],
            "path": record["path"][:80],
            "status": record["status"],
            "size": record["response_size"],
            "score": score,
            "has_list": has_struct_list(record["response_body_preview"]),
        })
    return results
```

### 3.5 inspect_request 分层返回

```python
def inspect_request_detail(captured, index):
    record = captured[index]
    preview = record["response_body_preview"]
    preview_str = json.dumps(preview, ensure_ascii=False)
    if len(preview_str) > 3000:
        preview = summarize_structure(preview)

    return {
        "method": record["method"],
        "url": record["url"],
        "request_headers": filter_headers(record["request_headers"]),
        "request_body": truncate_response(record.get("request_body"), max_array_items=1),
        "response_preview": preview,
        "response_size": record["response_size"],
    }

def summarize_structure(obj, depth=0):
    """只返回 JSON 的 key 结构，不返回值"""
    if depth > 2:
        return "..."
    if isinstance(obj, dict):
        return {k: summarize_structure(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        if obj and isinstance(obj[0], dict):
            return [summarize_structure(obj[0], depth + 1), f"...共{len(obj)}条"]
        return f"[{len(obj)} items]"
    return type(obj).__name__
```

---

## 四、工具集定义

Agent 共 7 个工具，按职责分三组。工具定义使用 OpenAI function calling 格式。

### 第一组：浏览器操控（本地，流量捕获分析用）

```python
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
                "required": ["url"]
            }
        }
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
                "required": ["action"]
            }
        }
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
            }
        }
    },
]
```

### 第二组：流量分析（本地，操作内存中的 captured 数据）

```python
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
            }
        }
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
                "required": ["request_index"]
            }
        }
    },
]
```

### 第三组：E2B 沙箱执行（云端，运行所有生成的代码）

```python
TOOLS += [
    {
        "type": "function",
        "function": {
            "name": "sandbox_write_file",
            "description": "在 E2B 沙箱中写入文件。用于写入爬虫脚本。目录不存在会自动创建。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "沙箱内文件路径，如 /home/user/crawler.py"},
                    "content": {"type": "string", "description": "文件内容"},
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_run_command",
            "description": (
                "在 E2B 沙箱中执行 shell 命令。用于安装依赖、运行爬虫、查看输出。"
                "沙箱已预装 Python 3.11、pip。Playwright + Chromium 按需安装。"
                "返回：exit_code、stdout（最后5000字符）、stderr（最后3000字符）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令"},
                    "timeout": {"type": "integer", "description": "超时秒数（默认120）"},
                },
                "required": ["command"]
            }
        }
    },
]
```

---

## 五、系统提示词

### 5.1 静态部分（可缓存）

```
你是一个招聘网站爬虫 Agent。用户给你目标招聘网站的 URL，你通过操控浏览器分析网络请求，生成 API 爬虫代码并在沙箱中运行，最终输出结构化的岗位数据。

# 核心目标

分析招聘网站的 HTTP API 请求，生成直接调用 API 的爬虫代码，获取所有岗位的完整详情信息。

# 三种场景及应对策略

## 场景 A：列表接口已包含完整详情
判断依据：inspect_request 查看列表接口响应时，列表项中的 requirements / responsibilities / description 等字段非空且内容完整。
策略：只需分析列表接口的分页机制，生成遍历所有页的爬虫代码即可。

## 场景 B：列表接口只有概述，详情需要单独请求
判断依据：列表项中详情字段为空或不存在，但从列表项可提取 ID 或详情 URL。
策略：
1. 在列表页用 browser_action 点击一个岗位，跳转到详情页
2. 用 get_traffic + inspect_request 找到详情页触发的详情 API
3. 生成爬虫代码：先遍历列表获取所有 ID → 再逐个请求详情 API → 合并数据

## 场景 C：网站有反爬保护（HTTP 直接请求返回 403 / 空响应 / 验证码）
判断依据：沙箱中运行 httpx 版爬虫失败，返回 403 或异常响应。
策略：将爬虫代码改为 Playwright 浏览器方案——在沙箱中启动无头浏览器，通过 page.on("response") 拦截 API 响应获取数据，用 page.click 实现自动翻页。请求由浏览器自身发出，绕过 JS 签名校验。

注意：场景 C 的 Playwright 爬虫代码同样在 E2B 沙箱中执行，需要先安装依赖：
pip install playwright && playwright install chromium

# 工作流程

## 第一步：捕获流量

1. browser_open 打开目标 URL
2. browser_screenshot 观察页面结构
3. browser_action 依次执行：
   - scroll 触发懒加载
   - 翻到第 2 页（触发分页接口）
   - 点击一个岗位进入详情页（触发详情接口）
4. get_traffic(min_score=4) 查看接口列表

## 第二步：分析接口

1. 对评分最高的接口 inspect_request，理解：
   - 请求参数（分页字段、筛选字段）
   - 响应结构（数据在哪个字段、分页信息在哪里）
2. 判断属于哪种场景：
   - 列表项是否包含 requirements、responsibilities 等详情字段？→ 场景 A
   - 如果不包含，是否已捕获到详情接口？→ 场景 B
   - 如果没有详情接口的流量 → 回到第一步，browser_action 点击一个岗位详情
   - 场景 C 在第四步执行爬虫失败后才能确认

## 第三步：生成代码

sandbox_write_file 写入爬虫脚本。代码要求：
- 使用 httpx（先尝试轻量方案）
- 实现自动翻页
- 如果是场景 B，实现列表遍历 + 逐条请求详情
- 频率控制（random.uniform(1, 3) 秒延迟）
- 错误处理（请求失败重试 2 次，仍失败则跳过）
- 只爬前 2 页用于验证
- 保存为 /home/user/output.json

## 第四步：执行与验证

1. sandbox_run_command 安装依赖：pip install httpx
2. sandbox_run_command 运行爬虫
3. 如果失败 → 读 stderr，分析错误，修复代码（见"错误修复"）
4. 如果成功 → sandbox_run_command 读取输出的前 3 条数据
5. 检验数据完整性：
   - title、location 是否非空？
   - requirements、responsibilities 是否非空？
   - 如果为空 → 说明是场景 B，需要补充详情爬取逻辑
6. 全部通过 → 任务完成

# 错误修复

执行失败时：
1. 仔细读 stderr，定位错误行和原因
2. 针对性修复，不要大范围重写
3. 常见对策：
   - 403/401 → 补全 headers（从 inspect_request 结果复制 Cookie、User-Agent 等）
   - 仍然 403 → 切换为 Playwright 方案（场景 C），需先在沙箱中安装：
     sandbox_run_command("pip install playwright && playwright install chromium")
   - ConnectionError → 增加 timeout 和重试
   - JSON 解析错误 → 打印原始响应查看实际格式
   - 数据为空 → 检查分页参数起始值（0 还是 1）
4. 最多修复 3 轮。3 轮后仍失败，向用户说明当前状态和原因

# Playwright 反爬方案模板（场景 C，在 E2B 沙箱中运行）

```python
import asyncio
import json
from playwright.async_api import async_playwright

results = []

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        async def handle_response(response):
            if "/api/target/path" in response.url and response.status == 200:
                data = await response.json()
                results.extend(data["list"])

        page.on("response", handle_response)
        await page.goto("https://target-url")
        await page.wait_for_timeout(3000)

        for i in range(N):
            await page.click("下一页选择器")
            await page.wait_for_timeout(2000)

        await browser.close()

    with open("/home/user/output.json", "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

asyncio.run(main())
```

# 行为约束

- 不要添加超出需求的功能。爬虫不需要 CLI 参数、日志框架、ORM
- 不要为假想场景做防御。只处理实际遇到的错误
- 不要过度注释。关键逻辑写注释，显而易见的代码不写
- 先诊断再行动。看到错误先分析，不要盲目重试
- 如果对页面结构不确定，先 browser_screenshot 看一眼
- 优先用 httpx 轻量方案。只有 HTTP 方案确实失败才切换 Playwright

# 输出风格

- 工具调用之间的文本控制在 1-2 句话
- 不要复述用户的需求
- 重点汇报：发现了什么接口、属于哪种场景、遇到什么问题
- 最终交付时简要说明爬虫的工作方式

# 输出数据格式

爬虫输出的每条岗位数据必须严格遵循以下 JSON 格式：

{
    "company": "公司名称",
    "id": "岗位ID（字符串）",
    "title": "岗位名称",
    "category": "岗位类别",
    "location": "工作地点",
    "requirements": "任职要求（完整文本）",
    "responsibilities": "岗位职责（完整文本）",
    "salary": "薪资范围（如无则填'未公开'）",
    "post_date": "发布日期（YYYY-MM-DD 格式）",
    "source_url": "岗位详情页的原始链接",
    "raw": {}
}

字段规则：
- 所有字段必须存在，不能缺失
- 无法获取的字段填空字符串 ""，不要填 null 或省略
- company 字段根据目标网站固定填写
- source_url 应拼接为完整的可访问 URL
- raw 保存 API 返回的原始数据，便于后续二次处理
```

### 5.2 动态部分（每会话注入）

```
────── __DYNAMIC_BOUNDARY__ ──────

# 环境
- 当前日期：{current_date}
- E2B 沙箱可用，Python 3.11，Playwright 按需安装
- 沙箱工作目录：/home/user
```

---

## 六、E2B 沙箱集成

### 6.1 沙箱管理器

```python
from e2b import Sandbox

class SandboxManager:
    def __init__(self):
        self.sandbox: Sandbox | None = None
        self._playwright_installed = False

    def ensure_sandbox(self) -> Sandbox:
        if self.sandbox is None:
            self.sandbox = Sandbox(timeout=600)
            # 预装 httpx（轻量，快）
            self.sandbox.commands.run("pip install httpx", timeout=30)
        return self.sandbox

    def ensure_playwright(self):
        """按需安装 Playwright（场景 C 才需要，避免每次都装）"""
        if not self._playwright_installed:
            sbx = self.ensure_sandbox()
            sbx.commands.run("pip install playwright", timeout=60)
            sbx.commands.run("playwright install chromium", timeout=120)
            self._playwright_installed = True

    def write_file(self, path: str, content: str) -> dict:
        sbx = self.ensure_sandbox()
        sbx.files.write(path, content)
        return {"status": "ok", "path": path, "size": len(content)}

    def run_command(self, command: str, timeout: int = 120) -> dict:
        sbx = self.ensure_sandbox()

        # 如果命令涉及 playwright，确保已安装
        if "playwright" in command.lower():
            self.ensure_playwright()

        result = sbx.commands.run(command, timeout=timeout)
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        return {
            "exit_code": result.exit_code,
            "stdout": stdout[-5000:] if len(stdout) > 5000 else stdout,
            "stderr": stderr[-3000:] if len(stderr) > 3000 else stderr,
        }

    def read_file(self, path: str) -> str:
        sbx = self.ensure_sandbox()
        return sbx.files.read(path)

    def kill(self):
        if self.sandbox:
            self.sandbox.kill()
            self.sandbox = None
```

### 6.2 工具执行路由

```python
browser_mgr = BrowserManager()      # 本地 Playwright（流量捕获分析）
sandbox_mgr = SandboxManager()      # E2B 云沙箱（运行生成的代码）

def execute_tool(name: str, args: dict) -> str:
    match name:
        # 本地浏览器工具（流量捕获阶段）
        case "browser_open":
            return json.dumps(asyncio.run(browser_mgr.open(args["url"])))
        case "browser_action":
            return json.dumps(asyncio.run(browser_mgr.action(**args)))
        case "browser_screenshot":
            # 返回 base64 图片，供多模态模型分析
            return browser_mgr.screenshot(args.get("full_page", False))

        # 本地流量分析工具（操作内存中的 captured 数据）
        case "get_traffic":
            return json.dumps(browser_mgr.get_traffic(args.get("min_score", 0)))
        case "inspect_request":
            return json.dumps(browser_mgr.inspect(args["request_index"]))

        # E2B 沙箱工具（执行所有生成的爬虫代码）
        case "sandbox_write_file":
            return json.dumps(sandbox_mgr.write_file(args["path"], args["content"]))
        case "sandbox_run_command":
            return json.dumps(sandbox_mgr.run_command(
                args["command"], args.get("timeout", 120)
            ))
```

---

## 七、可观测性（Agent 事件系统）

Agent Loop 在每一轮的关键节点发出事件，不同的 Handler 决定事件往哪里送。核心 Agent 逻辑和监控逻辑完全解耦。

### 7.1 事件流

```
Agent Loop 每轮循环
    │
    ├── on_llm_start       → LLM 接收了什么输入（消息数、总字符数、最新消息摘要）
    ├── on_llm_end         → LLM 返回了什么（文本内容 / tool_calls 列表 / token 用量）
    ├── on_tool_start      → 准备调用哪个工具，参数是什么
    ├── on_tool_end        → 工具返回了什么，耗时多少
    ├── on_error           → 哪里出错了
    └── on_agent_end       → Agent 结束（总轮次、总耗时）
```

### 7.2 事件数据结构

```python
from dataclasses import dataclass, field
from typing import Protocol
import time


@dataclass
class AgentEvent:
    """单个事件记录"""
    turn: int                    # 当前轮次
    event_type: str              # llm_start / llm_end / tool_start / tool_end / error / agent_end
    timestamp: float = field(default_factory=time.time)
    data: dict = field(default_factory=dict)
    duration_ms: float | None = None


class EventHandler(Protocol):
    """事件处理器接口"""
    def handle(self, event: AgentEvent) -> None: ...
```

### 7.3 终端调试输出（ConsoleHandler）

开发时最常用——在终端实时看到每一轮的决策链路：

```python
import json


class ConsoleHandler:
    """终端输出，开发调试用"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def handle(self, event: AgentEvent):
        t = event.turn
        match event.event_type:
            case "llm_start":
                msg_count = event.data.get("message_count", 0)
                total_chars = event.data.get("total_chars", 0)
                print(f"\n{'='*60}")
                print(f"🔄 Turn {t} | 发送 {msg_count} 条消息 (~{total_chars} 字符)")
                if self.verbose:
                    last = event.data.get("last_message", {})
                    role = last.get("role", "")
                    content = str(last.get("content", ""))[:200]
                    print(f"   最新消息 [{role}]: {content}")

            case "llm_end":
                content = event.data.get("content", "")
                tool_calls = event.data.get("tool_calls", [])
                duration = event.duration_ms or 0
                tokens = event.data.get("usage", {})

                if tool_calls:
                    print(f"🤖 LLM 响应 ({duration:.0f}ms, {tokens}):")
                    if content:
                        print(f"   💬 {content[:150]}")
                    for tc in tool_calls:
                        args_str = tc["arguments"][:100]
                        print(f"   🔧 调用 {tc['name']}({args_str}...)")
                else:
                    print(f"🤖 LLM 最终回复 ({duration:.0f}ms):")
                    print(f"   {content[:300]}")

            case "tool_start":
                name = event.data["name"]
                args = json.dumps(event.data["args"], ensure_ascii=False)
                if len(args) > 150:
                    args = args[:150] + "..."
                print(f"   ⚡ 执行 {name}: {args}")

            case "tool_end":
                name = event.data["name"]
                result = str(event.data.get("result", ""))
                duration = event.duration_ms or 0
                icon = "✅" if event.data.get("success", True) else "❌"
                print(f"   {icon} {name} 完成 ({duration:.0f}ms) → {result[:150]}")

            case "error":
                print(f"   ❗ 错误: {event.data.get('error', '')}")

            case "agent_end":
                total = event.data.get("total_turns", 0)
                total_time = event.data.get("total_time_ms", 0)
                print(f"\n{'='*60}")
                print(f"🏁 Agent 结束 | {total} 轮 | {total_time/1000:.1f}s")
```

终端输出示例：

```
============================================================
🔄 Turn 1 | 发送 2 条消息 (~3200 字符)
🤖 LLM 响应 (1523ms, {prompt: 1800, completion: 45}):
   🔧 调用 browser_open({"url": "https://join.qq.com/post.html"}...)
   ⚡ 执行 browser_open: {"url": "https://join.qq.com/post.html"}
   ✅ browser_open 完成 (4521ms) → {"title": "腾讯校园招聘", "captured_count": 5}

============================================================
🔄 Turn 2 | 发送 4 条消息 (~3800 字符)
   最新消息 [tool]: {"title": "腾讯校园招聘", "captured_count": 5}
🤖 LLM 响应 (980ms, {prompt: 2100, completion: 38}):
   🔧 调用 browser_screenshot({})
   ⚡ 执行 browser_screenshot: {}
   ✅ browser_screenshot 完成 (320ms) → data:image/png;base64,iVBOR...

============================================================
🔄 Turn 5 | 发送 12 条消息 (~8500 字符)
🤖 LLM 响应 (1102ms):
   💬 列表接口 requirements 为空，属于场景B。已捕获详情接口，生成爬虫代码。
   🔧 调用 sandbox_write_file({"path": "/home/user/crawler.py", "content": "import ht...)
   ⚡ 执行 sandbox_write_file: {"path": "/home/user/crawler.py"}
   ✅ sandbox_write_file 完成 (45ms) → {"status": "ok"}
...

============================================================
🏁 Agent 结束 | 9 轮 | 34.2s
```

### 7.4 JSON 文件日志（FileHandler）

每次会话完整记录为 JSONL 文件，便于回放和分析：

```python
from pathlib import Path
from datetime import datetime


class FileHandler:
    """JSONL 文件记录，每行一个事件"""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filepath = self.log_dir / f"agent_{ts}.jsonl"
        self.f = open(self.filepath, "a", encoding="utf-8")

    def handle(self, event: AgentEvent):
        line = json.dumps({
            "turn": event.turn,
            "type": event.event_type,
            "timestamp": event.timestamp,
            "duration_ms": event.duration_ms,
            "data": event.data,
        }, ensure_ascii=False, default=str)
        self.f.write(line + "\n")
        self.f.flush()

    def close(self):
        self.f.close()
```

### 7.5 使用方式

```python
# 开发调试：终端详细输出 + 文件记录
runner = AgentRunner(handlers=[
    ConsoleHandler(verbose=True),
    FileHandler(log_dir="logs"),
])
runner.run("爬取腾讯招聘所有岗位 https://join.qq.com/post.html")

# 生产运行：终端精简 + 文件记录
runner = AgentRunner(handlers=[
    ConsoleHandler(verbose=False),
    FileHandler(),
])

# 后续扩展：接入 Langfuse 等追踪平台，只需新增 Handler 实现
# runner = AgentRunner(handlers=[LangfuseHandler(), FileHandler()])
```

### 7.6 扩展说明

事件系统设计为可插拔的 Handler 模式，核心 Agent 逻辑不感知具体的监控实现。后续接入 Langfuse 等生产级追踪平台时，只需新增一个 `LangfuseHandler` 类实现 `handle` 方法，Agent 代码零改动。

---

## 八、Agent Loop 主循环

Agent Loop 封装为 `AgentRunner` 类，在每个关键节点通过 `emit` 发出事件。

```python
import os
import json
import time
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
)
MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
SYSTEM_PROMPT = SYSTEM_PROMPT_STATIC + "\n" + SYSTEM_PROMPT_DYNAMIC
MAX_TURNS = 30


class AgentRunner:
    def __init__(self, handlers: list[EventHandler] | None = None):
        self.handlers = handlers or [ConsoleHandler()]
        self.turn = 0

    def emit(self, event_type: str, data: dict = None, duration_ms: float = None):
        event = AgentEvent(
            turn=self.turn,
            event_type=event_type,
            data=data or {},
            duration_ms=duration_ms,
        )
        for h in self.handlers:
            h.handle(event)

    def run(self, user_message: str):
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
        agent_start = time.time()

        for self.turn in range(1, MAX_TURNS + 1):

            # ── 事件：LLM 调用前 ──
            self.emit("llm_start", {
                "message_count": len(messages),
                "total_chars": sum(len(json.dumps(m, ensure_ascii=False, default=str)) for m in messages),
                "last_message": messages[-1],
            })

            # ── 调用 LLM ──
            t0 = time.time()
            response = client.chat.completions.create(
                model=MODEL, messages=messages, tools=TOOLS,
            )
            msg = response.choices[0].message
            llm_ms = (time.time() - t0) * 1000

            # ── 事件：LLM 返回后 ──
            usage = {}
            if response.usage:
                usage = {
                    "prompt": response.usage.prompt_tokens,
                    "completion": response.usage.completion_tokens,
                }
            self.emit("llm_end", {
                "content": msg.content or "",
                "tool_calls": [
                    {"name": tc.function.name, "arguments": tc.function.arguments}
                    for tc in (msg.tool_calls or [])
                ],
                "usage": usage,
            }, duration_ms=llm_ms)

            # 追加 assistant 消息到历史
            assistant_msg = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ]
            messages.append(assistant_msg)

            # 无工具调用 → 结束
            if not msg.tool_calls:
                self.emit("agent_end", {
                    "total_turns": self.turn,
                    "total_time_ms": (time.time() - agent_start) * 1000,
                    "final_message": msg.content or "",
                })
                break

            # ── 执行工具调用 ──
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)

                # 事件：工具执行前
                self.emit("tool_start", {"name": name, "args": args})

                t1 = time.time()
                try:
                    raw_result = execute_tool(name, args)
                    tool_ms = (time.time() - t1) * 1000
                    # 事件：工具执行后
                    self.emit("tool_end", {
                        "name": name,
                        "result": raw_result[:500],
                        "success": True,
                    }, duration_ms=tool_ms)
                except Exception as e:
                    tool_ms = (time.time() - t1) * 1000
                    raw_result = json.dumps({"error": str(e)})
                    # 事件：工具执行出错
                    self.emit("error", {
                        "error": str(e),
                        "tool": name,
                    }, duration_ms=tool_ms)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": truncate_tool_result(raw_result),
                })

            # 上下文压缩
            messages = maybe_compress_history(messages)

        # 清理资源
        sandbox_mgr.kill()
        asyncio.run(browser_mgr.close())
        for h in self.handlers:
            if hasattr(h, "close"):
                h.close()


def truncate_tool_result(result: str, max_chars: int = 12000) -> str:
    if len(result) <= max_chars:
        return result
    head = max_chars * 2 // 3
    tail = max_chars // 3
    return (
        result[:head]
        + f"\n\n[...已截断，原始 {len(result)} 字符...]\n\n"
        + result[-tail:]
    )


def maybe_compress_history(messages: list, max_total_chars: int = 100000) -> list:
    """压缩早期工具结果，保留最近 16 条完整。"""
    total = sum(len(json.dumps(m, ensure_ascii=False, default=str)) for m in messages)
    if total < max_total_chars:
        return messages

    keep_recent = 16
    compressed = []
    for i, msg in enumerate(messages):
        if i >= len(messages) - keep_recent:
            compressed.append(msg)
            continue
        if msg.get("role") == "tool":
            content = msg.get("content", "")
            if len(content) > 300:
                msg = {**msg, "content": f"[早期结果已压缩，原始 {len(content)} 字符]"}
        compressed.append(msg)
    return compressed
```

---

## 九、BrowserManager（本地流量捕获）

```python
import asyncio
import base64
import json
import re
import time
from urllib.parse import urlparse
from playwright.async_api import async_playwright, Response

IGNORED_PATTERNS = [
    r"google-analytics", r"googletagmanager", r"doubleclick",
    r"facebook\.com/tr", r"hotjar", r"beacon", r"collect\?",
    r"log\?", r"track\?", r"\.(png|jpg|gif|css|woff2?|js)(\?|$)",
]
USEFUL_HEADERS = {
    "content-type", "accept", "authorization", "cookie",
    "referer", "origin", "user-agent",
    "x-csrf-token", "x-requested-with",
}

class BrowserManager:
    def __init__(self):
        self.pw = None
        self.browser = None
        self.page = None
        self.captured: list[dict] = []

    async def open(self, url: str) -> dict:
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

    async def action(self, action: str, **kwargs) -> dict:
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

    def screenshot(self, full_page: bool = False) -> str:
        buf = asyncio.run(self.page.screenshot(full_page=full_page))
        return base64.b64encode(buf).decode()

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
                "has_struct_list": _has_struct_list(r["response_body_preview"]),
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
            "request_headers": {k: v for k, v in r["request_headers"].items() if k.lower() in USEFUL_HEADERS},
            "request_body": r.get("request_body"),
            "response_preview": preview,
            "response_size": r["response_size"],
        }

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.pw:
            await self.pw.stop()
        self.browser = self.pw = self.page = None
```

---

## 十、项目文件结构

```
crawler-agent/
├── pyproject.toml
├── uv.lock
├── .env
├── src/
│   ├── __init__.py
│   ├── agent.py            # AgentRunner 主循环（第八章）
│   ├── llm.py              # OpenAI SDK 初始化 + 配置（第二章）
│   ├── browser.py          # BrowserManager 本地流量捕获（第九章）
│   ├── sandbox.py          # SandboxManager E2B 沙箱（第六章）
│   ├── tools.py            # 工具定义 + execute_tool 路由（第四章 + 第六章 6.2）
│   ├── traffic_utils.py    # 评分、截断、过滤函数（第三章）
│   ├── events.py           # AgentEvent + EventHandler 接口（第七章 7.2）
│   ├── handlers.py         # ConsoleHandler + FileHandler（第七章 7.3-7.4）
│   └── prompts.py          # 系统提示词拼接（第五章）
├── logs/                   # Agent 运行日志（JSONL 文件，gitignore）
└── README.md
```

### pyproject.toml

```toml
[project]
name = "crawler-agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "openai>=1.60.0",
    "playwright>=1.49.0",
    "e2b>=1.3.0",
    "python-dotenv>=1.0.0",
]
```

---

## 十一、设计检查清单

- [x] **LLM 兼容性**：OpenAI SDK 调用 DeepSeek，改 base_url 即可切换本地模型
- [x] **工具格式**：OpenAI function calling 格式，DeepSeek 原生支持
- [x] **数据清洗**：只留 200、数组截断前 2 条、请求头精简、摘要 vs 详情分层
- [x] **三种场景**：A（列表含详情）→ B（需详情接口）→ C（反爬 Playwright）
- [x] **沙箱隔离**：所有生成的代码（httpx + Playwright）都在 E2B 执行
- [x] **Playwright 按需安装**：场景 C 触发时才在沙箱中安装，避免浪费
- [x] **执行后验证**：检查关键字段是否非空
- [x] **自动修复**：分析 stderr，最多 3 轮
- [x] **输出格式**：12 字段严格匹配需求文档
- [x] **上下文控制**：工具结果截断 12000 字符 + 历史压缩保留最近 16 条
- [x] **可观测性**：事件钩子系统，ConsoleHandler 终端调试 + FileHandler JSONL 日志，可扩展接 Langfuse
- [x] **包管理**：uv 管理依赖