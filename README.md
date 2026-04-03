<p align="center">
  <img
    width="400"
    src="https://img.icons8.com/fluency/512/parse-from-clipboard.png"
    alt="JobMatcher Logo"
  />
</p>

<h1 align="center">
  智能岗位聚合与匹配平台
</h1>

<h4 align="center">
  自动爬取 · 智能匹配 · 多维对比 — 为技术求职者打造的一站式岗位分析工具
</h4>

<p align="center">
  <a href="#-功能特性">功能特性</a>
  ·
  <a href="#-技术架构">技术架构</a>
  ·
  <a href="#-快速开始">快速开始</a>
  ·
  <a href="#-部署指南">部署指南</a>
</p>

---

## 项目简介

在求职过程中，计算机科学及相关专业的求职者需要逐一访问各大互联网公司的招聘网站，手动浏览和筛选岗位信息，流程繁琐且效率低下。各公司的招聘网站没有统一的数据接口，页面结构各异，信息分散，难以横向对比。

**JobMatcher** 解决了这个问题——它能自动爬取多家公司的技术研发岗位，统一展示，并基于 LLM 提供智能匹配与对比分析，大幅提升求职效率。

## ✨ 功能特性

- **🕷️ 智能爬虫** — 基于 Playwright + ReAct Agent 循环，自动适配各公司招聘页面，无需手写爬虫规则
- **📊 岗位聚合** — 多公司岗位统一展示，支持按方向/地点/类型/日期多维筛选与搜索
- **🎯 智能匹配** — 上传简历 + 设定偏好，LLM 自动生成个性化推荐报告
- **⚖️ 岗位对比** — 收藏的意向岗位横向对比分析，辅助最终决策
- **💬 追问对话** — 报告生成后可继续向 LLM 追问，深入了解岗位细节
- **🔄 增量更新** — 基于 content hash 去重，定时采集仅处理新增或变动岗位

## 📸 页面预览

<!-- 如有截图可在此处添加 -->
<!-- <p align="center">
  <img src="docs/screenshots/jobs.png" width="80%" />
</p> -->

| 页面 | 说明 |
|------|------|
| `/jobs` | 岗位总览 — 公司选择 + 筛选 + 卡片列表 + 详情侧滑面板 |
| `/match` | 智能匹配 — 上传简历 + 偏好设置 + 流式推荐报告 + 追问对话 |
| `/compare` | 岗位对比 — 收藏岗位多维对比分析 + 追问对话 |
| `/settings` | 设置 — 目标公司管理 + 手动触发爬取 + 爬取状态监控 |

## 🏗️ 技术架构

### 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│           Next.js (App Router) + React + Tailwind CSS        │
│           shadcn/ui + assistant-ui + Zustand                 │
├──────────────────────────────────────────────────────────────┤
│                       REST API + SSE                         │
├──────────────────────────────────────────────────────────────┤
│                        Backend                               │
│              Python + FastAPI + aiosqlite                     │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ Routers │→ │ Services │→ │  Models  │→ │   SQLite    │  │
│  └─────────┘  └──────────┘  └──────────┘  └─────────────┘  │
│                    │               │                          │
│              ┌─────┴─────┐  ┌─────┴──────┐                  │
│              │  LLM API  │  │ Crawl Agent│                  │
│              │ (OpenAI)  │  │(Playwright)│                  │
│              └───────────┘  └────────────┘                  │
└──────────────────────────────────────────────────────────────┘
```

### 前端技术栈

| 技术 | 用途 |
|------|------|
| [Next.js](https://nextjs.org/) (App Router) | 框架 & 路由 |
| [React](https://react.dev/) 19 | UI 渲染 |
| [Tailwind CSS](https://tailwindcss.com/) 4 | 样式方案 |
| [shadcn/ui](https://ui.shadcn.com/) | 组件库 |
| [assistant-ui](https://www.assistant-ui.com/) | AI 对话组件 |
| [Zustand](https://zustand.docs.pmnd.rs/) | 状态管理 |
| [Bun](https://bun.sh/) | 包管理 & 运行时 |

### 后端技术栈

| 技术 | 用途 |
|------|------|
| [Python](https://python.org/) 3.11+ | 运行时 |
| [FastAPI](https://fastapi.tiangolo.com/) | Web 框架 |
| [SQLite](https://sqlite.org/) + aiosqlite | 数据库 |
| [Playwright](https://playwright.dev/) | 页面渲染 & 爬取 |
| [OpenAI API](https://platform.openai.com/) | LLM 调用 (解析/匹配/对比/对话) |
| [uv](https://docs.astral.sh/uv/) | 包管理 |

### 后端分层架构

```
Routers (路由层)     → 接收 HTTP 请求，参数校验，调用 Service
Services (业务层)    → 核心业务逻辑，调用 Models / LLM / Crawl
Models (数据层)      → 数据库读写操作
Schemas (校验层)     → Pydantic 请求/响应模型
Crawl (爬虫模块)     → ReAct Agent 循环 + Playwright 浏览器
LLM (AI 模块)        → OpenAI API 封装 (流式/非流式)
```

### 数据库设计

```
companies  ← 目标公司表 (id, name, career_url, crawl_interval)
jobs       ← 岗位表 (title, category, location, job_type, requirements, ...)
favorites  ← 收藏表 (job_id)
resume     ← 简历表 (单例，最多一行)
reports    ← 报告表 (match/compare 报告内容)
chat       ← 对话记录表
crawl_tasks← 爬取任务表 (状态跟踪)
```

### 支持的岗位方向 (15 类)

`Algorithm` · `Backend` · `Client` · `Frontend` · `Testing` · `BigData` · `Security` · `Hardware` · `ML` · `Infrastructure` · `Multimedia` · `CV` · `DevOps` · `DataMining` · `NLP`

## 🚀 快速开始

### 环境要求

| 工具 | 最低版本 |
|------|----------|
| [Node.js](https://nodejs.org/) | 18+ |
| [Bun](https://bun.sh/) | 1.0+ |
| [Python](https://python.org/) | 3.11+ |
| [uv](https://docs.astral.sh/uv/) | 0.1+ |

### 1. 克隆项目

```bash
git clone https://github.com/ZephyrusZhang/job-matcher.git
cd job-matcher
```

### 2. 后端配置

```bash
cd backend

# 安装依赖
uv sync

# 安装 Playwright 浏览器
uv run playwright install chromium

# 复制并编辑环境变量
cp .env.example .env
```

编辑 `.env` 文件，填入 API Key：

```env
# 用于报告生成、简历解析、对话 (OpenAI 兼容接口)
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1

# 用于爬虫 Agent 代码生成 (可使用 DeepSeek 等低成本模型)
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

### 3. 前端配置

```bash
cd frontend

# 安装依赖
bun install

# 复制并编辑环境变量
cp .env.example .env.local
```

编辑 `.env.local`：

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:3001
```

### 4. 启动开发服务器

在两个终端中分别运行：

```bash
# 终端 1：启动后端 (默认端口 3001)
cd backend
uv run uvicorn app.main:app --reload --port 3001

# 终端 2：启动前端 (默认端口 3000)
cd frontend
bun dev
```

打开浏览器访问 **http://localhost:3000** 即可使用。

## 📦 部署指南

### 后端部署

<details>
<summary>直接部署</summary>

```bash
cd backend

# 安装生产依赖
uv sync --no-dev

# 安装浏览器
uv run playwright install chromium --with-deps

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入生产环境的 API Key

# 启动服务
uv run uvicorn app.main:app --host 0.0.0.0 --port 3001
```

</details>

<details>
<summary>使用 systemd 管理 (Linux)</summary>

创建服务文件 `/etc/systemd/system/job-matcher-backend.service`：

```ini
[Unit]
Description=JobMatcher Backend
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/opt/job-matcher/backend
Environment=PATH=/opt/job-matcher/backend/.venv/bin:/usr/local/bin:/usr/bin
ExecStart=/opt/job-matcher/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 3001
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now job-matcher-backend
```

</details>

### 前端部署

<details>
<summary>静态构建 + Nginx</summary>

```bash
cd frontend

# 构建生产版本
bun run build

# 启动生产服务
bun start --port 3000
```

Nginx 反向代理配置示例：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # SSE 支持
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding on;
    }
}
```

</details>

## 🗂️ 项目结构

```
job-matcher/
├── frontend/                # Next.js 前端应用
│   ├── src/
│   │   ├── app/             # App Router 页面 (jobs, match, compare, settings)
│   │   ├── components/      # 业务组件 + shadcn/ui 组件
│   │   ├── hooks/           # 自定义 React Hooks
│   │   ├── store/           # Zustand 状态管理
│   │   ├── lib/             # API 调用层 + 工具函数
│   │   └── types/           # TypeScript 类型定义
│   └── package.json
├── backend/                 # FastAPI 后端服务
│   ├── app/
│   │   ├── routers/         # API 路由层
│   │   ├── services/        # 业务逻辑层
│   │   ├── models/          # 数据库模型
│   │   ├── schemas/         # Pydantic 校验模型
│   │   ├── crawl/           # 爬虫 Agent 模块
│   │   ├── llm/             # LLM 调用抽象层
│   │   └── main.py          # FastAPI 入口
│   ├── data/                # SQLite 数据库 + 上传文件
│   ├── config/              # YAML 配置文件
│   └── pyproject.toml
└── docs/                    # 项目文档
    ├── api-spec.md          # API 接口文档
    ├── frontend-architecture.md
    └── backend-architecture.md
```

## 🔧 开发指南

### API 文档

后端启动后，可通过以下地址查看自动生成的 API 文档：

- **Swagger UI**: http://localhost:3001/docs
- **ReDoc**: http://localhost:3001/redoc

详细的 API 规格请参阅 [`docs/api-spec.md`](docs/api-spec.md)。

### 架构文档

- [前端架构文档](docs/frontend-architecture.md) — 路由设计、状态管理、组件划分、数据流
- [后端架构文档](docs/backend-architecture.md) — 分层架构、数据库设计、爬虫管线、LLM 集成

### 常用命令

```bash
# 后端
cd backend
uv run uvicorn app.main:app --reload --port 3001   # 开发模式
uv run pytest                                        # 运行测试

# 前端
cd frontend
bun dev                                              # 开发模式
bun run build                                        # 生产构建
bun run lint                                         # 代码检查
```

## 📄 License

[MIT](LICENSE)
