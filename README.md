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

| 工具 | 最低版本 | 说明 |
|------|----------|------|
| [Docker](https://www.docker.com/) | 20+ | 部署 & 爬虫沙箱（必需） |
| [Bun](https://bun.sh/) | 1.0+ | 前端包管理（本地开发） |
| [Python](https://python.org/) | 3.11+ | 后端运行时（本地开发） |
| [uv](https://docs.astral.sh/uv/) | 0.1+ | 后端包管理（本地开发） |

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

### Docker 部署（推荐）

> 后端爬虫通过 Docker Socket 创建临时沙箱容器运行爬虫代码，因此宿主机必须安装 Docker。

#### 1. 准备环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# LLM API (报告生成、简历解析、爬虫 Agent)
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat

# 前端访问后端的地址（浏览器端发起请求）
# - 本地部署：                http://localhost:8000
# - 裸 IP 直连：               http://<服务器IP>:8000
# - 通过 Nginx 反代 + 域名：   https://<你的域名>（无需端口，走 /api/ 同源转发）
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

# 只读演示模式（可选，公网演示推荐开启）
# 开启后屏蔽 /match /compare /settings 三个功能，详见 "只读演示模式" 章节
# READ_ONLY_MODE=true
# NEXT_PUBLIC_READ_ONLY_MODE=true
```

#### 2. 构建爬虫沙箱镜像

```bash
docker compose build sandbox
```

> 沙箱镜像包含 Python 3.11 + httpx + Playwright + Chromium，供爬虫 Agent 在隔离环境中执行生成的爬虫代码。

#### 3. 启动服务

```bash
docker compose up -d --build
```

- 前端：http://localhost:3000
- 后端：http://localhost:8000

#### 4. 查看日志

```bash
docker compose logs -f backend   # 后端日志
docker compose logs -f frontend  # 前端日志
```

#### 架构说明

```
┌─────────────┐     ┌─────────────┐
│  frontend   │────▶│   backend   │
│  :3000      │     │   :8000     │
└─────────────┘     └──────┬──────┘
                           │ Docker Socket
                    ┌──────▼──────┐
                    │  sandbox    │  (按需创建/销毁)
                    │ containers  │
                    └─────────────┘
```

- **backend** 挂载 `/var/run/docker.sock`，通过 Docker SDK 按需创建沙箱容器执行爬虫
- 沙箱容器是宿主机上的 sibling 容器，运行完毕后自动清理
- `backend-data` volume 持久化 SQLite 数据库和上传的简历文件

---

### 直接部署

<details>
<summary>后端</summary>

```bash
cd backend

# 安装生产依赖
uv sync --no-dev

# 安装浏览器
uv run playwright install chromium --with-deps

# 构建爬虫沙箱镜像（需要 Docker）
docker build -f Dockerfile.sandbox -t crawler-sandbox .

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key

# 启动服务
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

</details>

<details>
<summary>前端（standalone 模式，推荐）</summary>

项目 `next.config.ts` 开启了 `output: "standalone"`，`bun run build` 之后会在 `.next/standalone/` 下生成一个自包含的 Node.js 服务器。但 Next.js 的 standalone 产物**不会自动拷贝** `.next/static/` 和 `public/`（官方设计：静态资源通常交给 CDN/反代，不强制塞进 standalone 目录），所以必须手动补齐，否则 `/_next/static/*` 和 `public` 下的静态文件会 404。

```bash
cd frontend

# 1. 安装依赖
bun install

# 2. 构建（NEXT_PUBLIC_* 必须在 build 时注入，否则被编译进 bundle 的是空值）
NEXT_PUBLIC_API_BASE_URL=https://<your-domain> bun run build

# 3. 把 static 资源和 public 目录手动拷贝到 standalone 产物里
#    - .next/static    → 编译产物（JS/CSS chunks、字体），必须放到 standalone/.next/static
#    - public          → 项目根 public 目录，standalone 运行时从当前工作目录读取
cp -r .next/static .next/standalone/.next/
cp -r public        .next/standalone/

# 4. 启动（指定监听端口，与 Nginx upstream 保持一致）
PORT=<frontend-port> node .next/standalone/server.js
```

> 如果使用 `bun start` 旧方式（依赖完整的 `.next` + `node_modules`），则不需要上面两次 `cp`；但镜像体积会显著更大，也不适合只打包产物分发的场景。

</details>

<details>
<summary>Nginx 反向代理（推荐，支持域名）</summary>

假设前端监听 `127.0.0.1:8848`、后端监听 `127.0.0.1:3001`，通过 Nginx 将两者统一暴露在同一个域名下：

```nginx
server {
    listen 80;
    server_name <your-domain>;   # 换成你的域名

    # 前端：Next.js 服务
    location / {
        proxy_pass http://127.0.0.1:<frontend-port>;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 后端 API：保留 /api/ 前缀原样转发
    # 访问 <your-domain>/api/jobs → 127.0.0.1:<backend-port>/api/jobs
    location /api/ {
        # 注意：proxy_pass 结尾不能带任何路径或斜杠，否则会吃掉 /api 前缀
        proxy_pass http://127.0.0.1:<backend-port>;

        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # FastAPI 流式响应 (SSE) 必须关闭缓冲
        proxy_buffering off;
        proxy_cache off;
    }
}
```

由于前后端挂在同一个域名下，前端构建时 `NEXT_PUBLIC_API_BASE_URL` 直接填域名即可（无需端口）：

```bash
NEXT_PUBLIC_API_BASE_URL=https://<your-domain> bun run build
```

建议再通过 `certbot --nginx -d <your-domain>` 申请 HTTPS 证书，以便 SSE 长连接与浏览器 Mixed-Content 策略兼容。

</details>

<details>
<summary>使用 systemd 管理后端 (Linux)</summary>

创建服务文件 `/etc/systemd/system/job-matcher-backend.service`：

```ini
[Unit]
Description=JobMatcher Backend
After=network.target docker.service

[Service]
Type=simple
User=deploy
WorkingDirectory=/opt/job-matcher/backend
Environment=PATH=/opt/job-matcher/backend/.venv/bin:/usr/local/bin:/usr/bin
ExecStart=/opt/job-matcher/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now job-matcher-backend
```

</details>

### 🔒 只读演示模式（Read-only Demo）

如果你希望将项目部署到**公网供访客浏览/体验**，但又不想暴露可写操作（例如避免被滥用触发 LLM 调用、公司 CRUD、爬虫任务等），可以开启**只读演示模式**。开启后：

- 前端会在 `/match`、`/compare`、`/settings` 三个页面覆盖一层蒙版，提示"该功能在演示环境中不可用，如需使用请自行部署"，页面布局和导航保持不变
- 后端会在中间件层直接返回 `403 READ_ONLY_MODE` 错误，拦截以下请求，**防止用户绕过前端直接调用 API**：
  - `/api/match/*`、`/api/compare/*`（所有 HTTP 方法，完整屏蔽）
  - `/api/settings`、`/api/companies`、`/api/crawl`、`/api/resume` 的所有写方法（POST / PUT / PATCH / DELETE）
- 公共只读接口（岗位列表、岗位详情、公司列表 GET、收藏读写等）仍然正常工作

前后端通过环境变量独立开关，本地开发时不设置即可恢复完整功能：

```env
# backend/.env（或 docker-compose.yml 的 environment）
READ_ONLY_MODE=true

# frontend 构建时注入（standalone 部署）
NEXT_PUBLIC_READ_ONLY_MODE=true bun run build
```

> ⚠️ `NEXT_PUBLIC_*` 变量会被 Next.js 编译进客户端 bundle，**必须在 `bun run build` 时注入**，运行时再改不会生效。
>
> 两个变量必须**同时开启**：只开前端会被用户改浏览器 JS 绕过，只开后端则蒙版不显示、用户点击按钮会看到原始 403 错误。

## 🗂️ 项目结构

```
job-matcher/
├── docker-compose.yml       # Docker 编排（前端 + 后端 + 沙箱构建）
├── .env.example             # Docker 环境变量模板
├── frontend/                # Next.js 前端应用
│   ├── Dockerfile           # 多阶段构建（Bun 构建 + Node 运行）
│   ├── src/
│   │   ├── app/             # App Router 页面 (jobs, match, compare, settings)
│   │   ├── components/      # 业务组件 + shadcn/ui 组件
│   │   ├── hooks/           # 自定义 React Hooks
│   │   ├── store/           # Zustand 状态管理
│   │   ├── lib/             # API 调用层 + 工具函数
│   │   └── types/           # TypeScript 类型定义
│   └── package.json
├── backend/                 # FastAPI 后端服务
│   ├── Dockerfile           # Python 3.11 + uv + Playwright
│   ├── Dockerfile.sandbox   # 爬虫沙箱镜像（httpx + Playwright + Chromium）
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
