# 后端架构文档

> 智能岗位聚合与匹配平台 — 后端技术架构
>
> 技术栈：Python + FastAPI + SQLite + Playwright + Crawl4AI + OpenAI API
>
> 包管理：uv

---

## 1. 项目目录结构

```
backend/
├── pyproject.toml              # uv 项目配置
├── config/
│   ├── companies.yml           # 种子公司配置（仅首次启动时迁移到数据库）
│   └── settings.yml            # 应用配置（LLM、调度、限制等）
├── app/
│   ├── main.py                 # FastAPI 入口，挂载路由 + 生命周期事件
│   ├── config.py               # 配置加载（YAML → Pydantic Settings）
│   ├── database.py             # SQLite 连接管理 + 建表初始化
│   ├── dependencies.py         # FastAPI 依赖注入（db session, services）
│   ├── exceptions.py           # 自定义异常 + 全局异常处理器
│   ├── schemas/                # Pydantic Request/Response 模型（数据校验层）
│   │   ├── common.py           # ApiResponse 信封、PaginationMeta
│   │   ├── job.py
│   │   ├── company.py
│   │   ├── favorite.py
│   │   ├── resume.py
│   │   ├── report.py
│   │   ├── chat.py
│   │   └── crawl.py
│   ├── models/                 # 数据库模型（SQLite 表映射，纯数据类）
│   │   ├── company.py
│   │   ├── job.py
│   │   ├── favorite.py
│   │   ├── resume.py
│   │   ├── report.py
│   │   ├── chat.py
│   │   └── crawl_task.py
│   ├── routers/                # 路由层（薄层，仅参数校验 + 调用 service）
│   │   ├── companies.py        # GET/POST/PUT/DELETE /api/companies
│   │   ├── jobs.py             # GET /api/jobs, /api/jobs/{id}, /search, /suggest
│   │   ├── favorites.py        # POST/DELETE/GET /api/favorites
│   │   ├── resume.py           # POST/GET/DELETE /api/resume
│   │   ├── match.py            # POST /api/match/generate, GET /api/match/report
│   │   ├── compare.py          # POST /api/compare/generate, GET /api/compare/report
│   │   ├── chat.py             # POST /api/chat/message, GET /api/chat/history
│   │   ├── crawl.py            # POST /api/crawl/trigger, GET /api/crawl/tasks
│   │   └── settings.py         # GET/PATCH /api/settings
│   ├── services/               # 业务逻辑层（核心逻辑）
│   │   ├── company_service.py  # 公司 CRUD + 内存缓存 + 爬取状态查询
│   │   ├── job_service.py      # 岗位查询、搜索、自动补全
│   │   ├── favorite_service.py # 收藏增删查 + 概要统计
│   │   ├── resume_service.py   # 上传覆盖 + 级联清空 + 解析
│   │   ├── report_service.py   # 匹配/对比报告生成（SSE 流式）
│   │   ├── chat_service.py     # 追问对话（SSE 流式）
│   │   ├── crawl_service.py    # 爬取任务管理与执行
│   │   └── settings_service.py # 用户偏好读写
│   ├── crawl/                  # 通用爬虫管线模块
│   │   ├── pipeline.py         # 核心管线：Playwright → Crawl4AI → LLM
│   │   ├── browser.py          # Playwright 浏览器管理（单例复用）
│   │   ├── extractor.py        # Crawl4AI 内容提取封装
│   │   ├── scheduler.py        # APScheduler 定时调度
│   │   └── dedup.py            # 增量去重（基于 content hash）
│   ├── llm/                    # LLM 调用抽象层
│   │   ├── client.py           # OpenAI API 客户端封装（流式/非流式）
│   │   ├── prompts/            # Prompt 模板
│   │   │   ├── parse_job.py    # 岗位结构化解析 prompt
│   │   │   ├── parse_resume.py # 简历解析 prompt
│   │   │   ├── match.py        # 智能匹配报告生成 prompt
│   │   │   ├── compare.py      # 岗位对比报告生成 prompt
│   │   │   └── chat.py         # 追问对话 prompt
│   │   └── context.py          # 上下文管理（token 计数 + 截断策略）
│   └── utils/
│       ├── file_parser.py      # PDF/DOCX 文本提取
│       └── text.py             # 文本工具（清洗、摘要）
├── data/
│   ├── job_matcher.db          # SQLite 数据库文件（运行时生成）
│   └── uploads/                # 简历上传存储目录
└── tests/
```

### 分层职责

| 层 | 职责 | 原则 |
|----|------|------|
| `routers/` | 接收 HTTP 请求，参数校验，调用 service，返回响应 | 不含业务逻辑 |
| `services/` | 核心业务逻辑，调用 models / llm / crawl | 不直接处理 HTTP |
| `models/` | 数据库读写操作 | 纯数据访问，不含业务判断 |
| `schemas/` | Pydantic 模型，请求/响应数据校验 | 不含逻辑 |
| `crawl/` | 爬虫管线 | 只被 crawl_service 调用 |
| `llm/` | LLM 调用 | 只被 services 调用 |

---

## 2. SQLite 表设计

### 2.0 companies — 公司表

```sql
CREATE TABLE companies (
    id                   TEXT PRIMARY KEY,              -- 公司唯一标识（如 bytedance）
    name                 TEXT NOT NULL,                 -- 公司中文名称
    career_url           TEXT NOT NULL,                 -- 招聘页 URL
    crawl_interval_hours INTEGER NOT NULL DEFAULT 12,   -- 采集频率（小时）
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
);
```

> 首次启动时自动从 `config/companies.yml` 迁移种子数据到此表。后续通过 API 管理。

### 2.1 jobs — 岗位表

```sql
CREATE TABLE jobs (
    id                 TEXT PRIMARY KEY,                -- UUID
    company_id         TEXT NOT NULL,                   -- 对应 companies 表中的公司 id
    title              TEXT NOT NULL,                   -- 岗位名称
    category           TEXT NOT NULL,                   -- 岗位方向（算法/后端/前端/...）
    location           TEXT,                            -- 工作地点
    job_type           TEXT,                            -- fulltime/intern/parttime/contract
    responsibilities   TEXT,                            -- 核心职责
    requirements_must  TEXT,                            -- JSON array: ["React", "TypeScript"]
    requirements_nice  TEXT,                            -- JSON array: ["GraphQL"]
    department         TEXT,                            -- 所属部门
    department_product TEXT,                            -- 部门产品
    education          TEXT,                            -- 学历要求
    experience         TEXT,                            -- 经验要求
    posted_date        TEXT,                            -- 发布日期 ISO date
    source_url         TEXT NOT NULL,                   -- 原始招聘页链接
    summary            TEXT,                            -- LLM 生成的一句话概述
    content_hash       TEXT NOT NULL,                   -- SHA-256，用于增量去重
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_jobs_company      ON jobs(company_id);
CREATE INDEX idx_jobs_category     ON jobs(category);
CREATE INDEX idx_jobs_location     ON jobs(location);
CREATE INDEX idx_jobs_job_type     ON jobs(job_type);
CREATE INDEX idx_jobs_posted_date  ON jobs(posted_date DESC);
CREATE INDEX idx_jobs_content_hash ON jobs(content_hash);
```

### 2.2 favorites — 收藏表

```sql
CREATE TABLE favorites (
    job_id     TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (job_id)
);
```

### 2.3 resume — 简历表（单例，最多一行）

```sql
CREATE TABLE resume (
    id          INTEGER PRIMARY KEY CHECK (id = 1),  -- 强制单行
    filename    TEXT NOT NULL,                        -- 上传文件名
    file_path   TEXT NOT NULL,                        -- 存储路径
    parsed_data TEXT NOT NULL,                        -- JSON: {skills, experience_years, education, raw_text}
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 2.4 reports — 报告表

```sql
CREATE TABLE reports (
    id          TEXT PRIMARY KEY,                     -- UUID
    company_id  TEXT NOT NULL,                        -- 公司 ID
    report_type TEXT NOT NULL,                        -- 'match' | 'compare'
    content     TEXT NOT NULL,                        -- 完整报告 Markdown 内容
    job_ids     TEXT NOT NULL,                        -- JSON array: 关联的岗位 ID 列表
    preferences TEXT NOT NULL,                        -- JSON: {interest, additional}
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(company_id, report_type)                   -- 每公司每类型仅保留一份
);
```

### 2.5 chat_messages — 对话消息表

```sql
CREATE TABLE chat_messages (
    id         TEXT PRIMARY KEY,                      -- UUID
    report_id  TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    role       TEXT NOT NULL,                         -- 'user' | 'assistant'
    content    TEXT NOT NULL,                         -- 消息内容
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_chat_report ON chat_messages(report_id, created_at);
```

### 2.6 crawl_tasks — 爬取任务表

```sql
CREATE TABLE crawl_tasks (
    id            TEXT PRIMARY KEY,                   -- UUID
    company_id    TEXT NOT NULL,                      -- 公司 ID
    status        TEXT NOT NULL DEFAULT 'pending',    -- pending/running/completed/failed
    jobs_found    INTEGER DEFAULT 0,                  -- 发现岗位总数
    jobs_new      INTEGER DEFAULT 0,                  -- 新增岗位数
    jobs_updated  INTEGER DEFAULT 0,                  -- 更新岗位数
    error_message TEXT,                               -- 错误信息（仅 failed）
    started_at    TEXT,
    completed_at  TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_crawl_company ON crawl_tasks(company_id, created_at DESC);
```

### 2.7 settings — 用户设置表（单例）

```sql
CREATE TABLE settings (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    display_density TEXT NOT NULL DEFAULT 'comfortable',  -- comfortable/compact
    language        TEXT NOT NULL DEFAULT 'zh'             -- zh/en
);
```

### 级联删除关系

```
resume 上传/删除
  └──▶ DELETE FROM reports          （所有报告）
         └──▶ DELETE FROM chat_messages  （ON DELETE CASCADE 自动级联）

report 重新生成（某公司某类型）
  └──▶ DELETE FROM reports WHERE company_id=? AND report_type=?
         └──▶ DELETE FROM chat_messages  （ON DELETE CASCADE 自动级联）
```

---

## 3. 通用爬虫管线

### 3.1 核心理念

**零适配器设计**：不为每家公司编写单独的适配器/adapter。用户只需在前端设置页面添加公司名称和招聘页 URL，系统通过统一管线完成全部流程。

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Scheduler   │────▶│  Playwright   │────▶│  Crawl4AI     │────▶│  LLM         │
│ (APScheduler)│     │ (渲染页面)    │     │ (提取内容)    │     │ (结构化解析)  │
└─────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                                                      │
                                                               ┌──────▼──────┐
                                                               │ Dedup +      │
                                                               │ Upsert DB    │
                                                               └─────────────┘
```

### 3.2 pipeline.py — 核心管线

```python
async def crawl_company(company: CompanyConfig) -> CrawlResult:
    """通用爬取管线，对所有公司统一执行"""

    # Step 1: Playwright 渲染
    # - 打开 career_url，等待动态内容加载完成
    # - 自动滚动加载（处理懒加载/无限滚动），最多 max_scroll_attempts 次
    # - 截获所有岗位详情页链接
    # - 逐一访问详情页，收集完整 HTML
    html_pages = await browser.render_and_collect(company.career_url)

    # Step 2: Crawl4AI 提取
    # - 从渲染后的 HTML 中提取正文内容
    # - 去除导航栏、侧边栏、footer 等噪音
    # - 输出清洗后的文本块列表（每个岗位一个文本块）
    raw_contents = await extractor.extract(html_pages)

    # Step 3: LLM 结构化解析
    # - 将原始文本转换为统一 Job Schema 的结构化 JSON
    # - 批量处理，每次发送多个岗位文本以节省 API 调用
    # - 自动过滤非技术岗位（产品、设计、运营等）
    # - category 必须从预定义的 15 个方向中选择
    jobs = await llm_client.parse_jobs(raw_contents, company_name=company.name)

    # Step 4: 增量去重 + 入库
    # - 计算 content_hash（基于 title + responsibilities + requirements）
    # - hash 不存在 → INSERT（新岗位）
    # - hash 存在但其他字段有变化 → UPDATE（更新）
    # - hash 完全匹配 → SKIP（跳过）
    result = await dedup.upsert_jobs(jobs, company_id=company.id)

    return result  # CrawlResult(jobs_found, jobs_new, jobs_updated)
```

### 3.3 browser.py — Playwright 浏览器管理

```python
class BrowserManager:
    """单例管理 Playwright 浏览器实例，避免重复启动"""

    async def init(self):
        """应用启动时初始化浏览器（headless 模式）"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)

    async def render_and_collect(self, career_url: str) -> list[str]:
        """
        1. 创建新 page，导航到 career_url
        2. 等待页面加载完成（networkidle 或自定义选择器）
        3. 自动滚动触发懒加载，收集所有岗位列表项
        4. 提取每个岗位的详情页链接
        5. 逐一访问详情页，返回所有页面的 HTML
        """

    async def close(self):
        """应用关闭时清理浏览器资源"""
```

### 3.4 extractor.py — Crawl4AI 内容提取

```python
class ContentExtractor:
    """封装 Crawl4AI，从 HTML 提取结构化文本"""

    async def extract(self, html_pages: list[str]) -> list[str]:
        """
        对每个 HTML 页面：
        1. 使用 Crawl4AI 的内容提取策略
        2. 去除导航、侧边栏、footer 等非正文内容
        3. 输出清洗后的纯文本
        返回文本块列表（每个岗位一个文本块）
        """
```

### 3.5 scheduler.py — 定时调度

```python
class CrawlScheduler:
    """基于 APScheduler 的定时爬取调度"""

    def __init__(self, companies: list[CompanyConfig]):
        self.scheduler = AsyncIOScheduler()

    def start(self):
        """
        应用启动时注册所有公司的定时任务：
        - 读取每家公司的 crawl_interval_hours
        - 为每家公司添加 IntervalTrigger 定时任务
        - 首次启动时立即执行一次
        """
        for company in self.companies:
            self.scheduler.add_job(
                crawl_company, 'interval',
                hours=company.crawl_interval_hours,
                args=[company],
                id=f"crawl_{company.id}"
            )
        self.scheduler.start()

    async def trigger_manual(self, company_id: str):
        """手动触发某公司的爬取（POST /api/crawl/trigger 调用）"""
```

### 3.6 dedup.py — 增量去重

```python
import hashlib

def compute_content_hash(title: str, responsibilities: str, requirements_must: list[str]) -> str:
    """基于岗位核心内容生成 SHA-256，用于判断新增/变更/重复"""
    payload = f"{title}|{responsibilities}|{'|'.join(sorted(requirements_must))}"
    return hashlib.sha256(payload.encode()).hexdigest()

async def upsert_jobs(jobs: list[ParsedJob], company_id: str) -> CrawlResult:
    """
    对每个解析出的岗位：
    1. 计算 content_hash
    2. 查询 DB 是否存在相同 hash
       - 不存在 → INSERT，计入 jobs_new
       - 存在但其他字段变化 → UPDATE，计入 jobs_updated
       - 完全匹配 → SKIP
    3. 返回统计结果
    """
```

---

## 4. LLM 调用层抽象

### 4.1 client.py — 统一客户端

```python
from openai import AsyncOpenAI

class LLMClient:
    """封装 OpenAI API 调用，统一处理流式/非流式"""

    def __init__(self, config: LLMConfig):
        self.client = AsyncOpenAI(api_key=config.api_key)
        self.model = config.model                  # gpt-4o-mini（解析类）
        self.model_report = config.model_report    # gpt-4o（报告/对话类）

    async def structured_parse(self, messages: list[dict], schema: dict) -> dict:
        """
        非流式调用，返回结构化 JSON。
        用于：岗位结构化解析、简历解析。
        使用 response_format={"type": "json_object"} 保证输出为合法 JSON。
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3  # 解析类任务低温度，确保准确性
        )
        return json.loads(response.choices[0].message.content)

    async def stream_generate(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """
        流式调用，yield 文本 chunk。
        用于：报告生成、追问对话。
        """
        stream = await self.client.chat.completions.create(
            model=self.model_report,
            messages=messages,
            stream=True,
            temperature=0.7
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
```

### 4.2 Prompt 设计

#### parse_job.py — 岗位结构化解析

```
系统提示：
你是一个岗位信息结构化解析器。你将收到某公司招聘页面的原始文本内容。

任务：
1. 识别并提取所有技术研发类岗位
2. 过滤非技术岗位（产品、设计、运营、市场、HR、财务等）
3. 对每个技术岗位输出以下字段的 JSON：
   - title: 岗位名称
   - category: 岗位方向，必须从以下选项中选择：
     算法/后端/客户端/前端/测试/大数据/安全/硬件/机器学习/基础架构/多媒体/计算机视觉/运维/数据挖掘/自然语言处理
   - location: 工作地点
   - job_type: fulltime/intern/parttime/contract
   - responsibilities: 核心职责描述
   - requirements_must: 必备技能列表（string array）
   - requirements_nice: 加分技能列表（string array）
   - department: 所属部门
   - department_product: 部门负责的产品
   - education: 学历要求
   - experience: 经验要求
   - posted_date: 发布日期（ISO date 格式，无法确定则为 null）
   - source_url: 原始链接
   - summary: 一句话概述（20字以内）

输出格式：
{"jobs": [<Job>, <Job>, ...]}

公司名称：{company_name}
原始内容：
{raw_content}
```

#### parse_resume.py — 简历解析

```
系统提示：
你是一个简历解析器。你将收到一份简历的纯文本内容。

任务：提取以下结构化信息：
- skills: 技术技能列表（string array，如 ["React", "TypeScript", "Python"]）
- experience_years: 工作经验年限（integer，无法确定则为 null）
- education: 最高学历及专业（如 "本科 计算机科学"，无法确定则为 null）

输出格式：
{"skills": [...], "experience_years": N, "education": "..."}

简历内容：
{raw_text}
```

#### match.py — 智能匹配报告

```
系统提示：
你是一位资深技术招聘顾问，正在帮助求职者从收藏的岗位中找到最适合的岗位。

上下文信息：
- 用户简历：{parsed_resume}（包含技能、经验、教育背景）
- 用户偏好：{preferences}（包含兴趣方向和其他要求）
- 候选岗位列表：{favorited_jobs}（该公司所有收藏岗位的完整信息）

任务：
1. 综合分析用户的技能、经验、教育背景和偏好
2. 将候选岗位按推荐程度从高到低排序
3. 对每个岗位进行详细分析

每个岗位的分析包括以下四个维度：
- 推荐理由：为什么推荐该岗位，与用户技能、经验、偏好的契合点
- 岗位前景：该岗位的发展前景、团队实力、产品影响力
- 技术栈分析：该岗位的技术栈与用户现有技能的匹配情况
- 潜在不足：该岗位与用户预期可能存在的差距

输出格式：Markdown，使用以下格式：

🏅 推荐 #N  {岗位名称}

📌 推荐理由
...

📈 岗位前景
...

🛠️ 技术栈分析
...

⚠️ 潜在不足
...
```

#### compare.py — 岗位对比报告

```
系统提示：
你是一位资深技术招聘顾问，正在帮助求职者对比意向岗位，做出最终选择。

上下文信息（同匹配）

任务：
1. 综合分析用户背景
2. 横向对比所有收藏岗位
3. 按推荐程度排序，每个岗位分析：
   - 推荐理由：相比其他岗位的优势
   - 岗位前景：发展前景与成长空间
   - 技术栈分析：与其他岗位的技术栈差异
   - 相对优势：该岗位相对于其他岗位的亮点
   - 相对不足：该岗位相对于其他岗位的短板
4. 末尾给出综合建议

输出格式：Markdown，使用以下格式：

🏅 推荐 #N  {岗位名称}

📌 推荐理由
...

📈 岗位前景
...

🛠️ 技术栈分析
...

✅ 相对优势
...

⚠️ 相对不足
...

（所有岗位分析完成后）

💡 综合建议
...
```

#### chat.py — 追问对话

```
系统提示：
你是一位资深技术招聘顾问，正在为用户提供岗位咨询。
你拥有用户的简历信息、岗位偏好、已生成的分析报告以及候选岗位的详细信息。
请基于这些上下文回答用户的问题。回答要具体、有针对性，避免泛泛而谈。

上下文：
- 用户简历：{parsed_resume}
- 用户偏好：{preferences}
- 已生成报告：{report_content}
- 候选岗位详情：{jobs_detail}
```

### 4.3 context.py — 上下文管理

```python
class ContextManager:
    """管理 LLM 调用的上下文窗口"""

    def build_chat_messages(self, report_id: str, new_message: str) -> list[dict]:
        """
        组装追问对话的 messages 列表。

        消息结构：
        1. system prompt（固定，含角色定义）
        2. system context（简历 + 偏好 + 报告内容 + 岗位详情）— 始终保留
        3. 对话历史 — 滑动窗口，保留最近 10 轮
        4. 当前用户消息

        Token 预算分配（以 gpt-4o 为例）：
        - system context（简历+报告+岗位）: ~3000 tokens
        - 对话历史: ~3000 tokens
        - 用户消息 + 回复预留: ~2000 tokens
        - 总计控制在 ~8K tokens
        """

    def truncate_history(self, messages: list[dict], max_rounds: int = 10) -> list[dict]:
        """
        保留最近 N 轮对话，超出部分丢弃最早的消息。
        一轮 = 一条 user + 一条 assistant。
        """

    def estimate_tokens(self, text: str) -> int:
        """使用 tiktoken 估算 token 数量"""
```

---

## 5. 简历解析

### 5.1 file_parser.py — 文件文本提取

```python
class FileParser:
    @staticmethod
    async def extract_text(file_path: str, filename: str) -> str:
        """
        根据文件扩展名选择解析方式：
        - .pdf → pdfplumber 提取文本
        - .docx → python-docx 提取文本
        返回纯文本内容。
        """
        ext = Path(filename).suffix.lower()
        if ext == '.pdf':
            return _extract_pdf(file_path)
        elif ext == '.docx':
            return _extract_docx(file_path)
        else:
            raise FileFormatError()
```

### 5.2 resume_service.py — 简历服务

```python
class ResumeService:
    async def upload(self, file: UploadFile) -> ResumeResponse:
        """
        完整上传流程：
        1. 校验文件格式和大小
        2. 保存文件到 data/uploads/（覆盖旧文件）
        3. FileParser 提取纯文本
        4. LLM 结构化解析（提取技能、经验、教育背景）
        5. INSERT OR REPLACE 到 resume 表（id=1，强制单行）
        6. 级联清空：DELETE FROM reports（chat_messages 通过 ON DELETE CASCADE 自动清除）
        7. 返回解析结果 + 清空统计
        """

    async def get(self) -> ResumeInfo | None:
        """查询当前简历，未上传返回 None"""

    async def delete(self) -> ClearResult:
        """删除简历文件和数据库记录，级联清空报告和对话"""
```

---

## 6. 配置管理

### 6.1 config/settings.yml

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  cors_origins: ["http://localhost:3000"]

database:
  path: "data/job_matcher.db"

uploads:
  dir: "data/uploads"
  max_size_mb: 10
  allowed_types:
    - "application/pdf"
    - "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

llm:
  api_key: "${OPENAI_API_KEY}"         # 支持环境变量引用
  model: "gpt-4o-mini"                 # 岗位解析、简历解析（低成本）
  model_report: "gpt-4o"               # 报告生成、追问对话（高质量）
  max_tokens_report: 4096
  max_tokens_chat: 2048
  temperature: 0.7

crawl:
  browser_headless: true
  page_load_timeout: 30000             # 毫秒
  max_scroll_attempts: 20              # 最大滚动次数（处理懒加载）
  concurrent_companies: 2              # 同时爬取的公司数
```

### 6.2 config/companies.yml（种子数据）

> 此文件仅在数据库 `companies` 表为空时用于初始化种子数据。后续公司管理通过 API 进行。

```yaml
companies:
  - id: bytedance
    name: 字节跳动
    career_url: "https://jobs.bytedance.com/campus/position"
    crawl_interval_hours: 12

  - id: tencent
    name: 腾讯
    career_url: "https://join.qq.com/post.html"
    crawl_interval_hours: 24

  - id: xiaohongshu
    name: 小红书
    career_url: "https://job.xiaohongshu.com/campus"
    crawl_interval_hours: 12
```

### 6.3 config.py — 配置加载

```python
from pydantic import BaseModel
import yaml, os, re

class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]

class DatabaseConfig(BaseModel):
    path: str = "data/job_matcher.db"

class UploadConfig(BaseModel):
    dir: str = "data/uploads"
    max_size_mb: int = 10
    allowed_types: list[str]

class LLMConfig(BaseModel):
    api_key: str
    model: str = "gpt-4o-mini"
    model_report: str = "gpt-4o"
    max_tokens_report: int = 4096
    max_tokens_chat: int = 2048
    temperature: float = 0.7

class CrawlConfig(BaseModel):
    browser_headless: bool = True
    page_load_timeout: int = 30000
    max_scroll_attempts: int = 20
    concurrent_companies: int = 2

class AppConfig(BaseModel):
    server: ServerConfig
    database: DatabaseConfig
    uploads: UploadConfig
    llm: LLMConfig
    crawl: CrawlConfig

def load_config() -> AppConfig:
    """
    加载配置：
    1. 读取 config/settings.yml
    2. 解析 ${ENV_VAR} 占位符，替换为环境变量值
    3. 用 Pydantic 校验并返回 AppConfig 实例
    注意：公司配置已移至数据库，不再从 YAML 加载。
    """
```

---

## 7. 错误处理

### 7.1 自定义异常

```python
# app/exceptions.py

class AppError(Exception):
    """基础业务异常"""
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code

class ResumeNotFoundError(AppError):
    def __init__(self):
        super().__init__("RESUME_NOT_FOUND", "请先上传简历", 422)

class NoFavoritesError(AppError):
    def __init__(self):
        super().__init__("NO_FAVORITES", "该公司暂无收藏岗位", 422)

class CrawlInProgressError(AppError):
    def __init__(self):
        super().__init__("CRAWL_IN_PROGRESS", "该公司已有正在进行的爬取任务", 409)

class FileFormatError(AppError):
    def __init__(self):
        super().__init__("UNSUPPORTED_FORMAT", "仅支持 PDF 和 DOCX 格式", 415)

class FileTooLargeError(AppError):
    def __init__(self):
        super().__init__("FILE_TOO_LARGE", "文件大小不能超过 10MB", 413)

class JobNotFoundError(AppError):
    def __init__(self):
        super().__init__("JOB_NOT_FOUND", "岗位不存在", 404)

class ReportNotFoundError(AppError):
    def __init__(self):
        super().__init__("REPORT_NOT_FOUND", "报告不存在", 404)

class CompanyNotFoundError(AppError):
    def __init__(self):
        super().__init__("COMPANY_NOT_FOUND", "公司不存在", 404)

class CompanyExistsError(AppError):
    def __init__(self):
        super().__init__("COMPANY_EXISTS", "公司ID已存在", 409)
```

### 7.2 全局异常处理器

```python
# app/main.py 中注册

@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "error": {"code": exc.code, "message": exc.message},
            "pagination": None
        }
    )

@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    logger.exception("Unexpected error")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "error": {"code": "INTERNAL_ERROR", "message": "服务器内部错误"},
            "pagination": None
        }
    )
```

---

## 8. 关键依赖清单

```
# Web 框架
fastapi
uvicorn[standard]

# 数据校验 + 配置
pydantic
pydantic-settings

# 数据库
aiosqlite

# LLM
openai
tiktoken

# 爬虫
playwright
crawl4ai

# 定时任务
apscheduler

# 文件解析
pdfplumber
python-docx

# 配置
pyyaml

# 文件上传
python-multipart
```

---

## 9. 应用生命周期

```python
# app/main.py

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动阶段
    config = load_config()
    await init_database(config.database)       # 创建表（IF NOT EXISTS）
    await browser_manager.init()               # 启动 Playwright 浏览器
    crawl_scheduler.start()                    # 启动定时爬取调度

    yield

    # 关闭阶段
    crawl_scheduler.stop()
    await browser_manager.close()

app = FastAPI(title="JobMatcher API", lifespan=lifespan)

# 挂载路由
app.include_router(companies_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(favorites_router, prefix="/api")
app.include_router(resume_router, prefix="/api")
app.include_router(match_router, prefix="/api")
app.include_router(compare_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(crawl_router, prefix="/api")
app.include_router(settings_router, prefix="/api")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.server.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
