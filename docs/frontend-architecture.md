# 前端架构文档

> 智能岗位聚合与匹配平台 — 前端技术架构
>
> 技术栈：React + Next.js (App Router) + Tailwind CSS + shadcn/ui + assistant-ui + Zustand
>
> 包管理：Bun

---

## 1. 项目目录结构

```
frontend/
├── package.json
├── bun.lock
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── components.json              # shadcn/ui 配置
├── .env.local                   # NEXT_PUBLIC_API_BASE_URL（指向真实后端或 mock server）
├── .env.example
├── public/
│   └── favicon.ico
├── src/
│   ├── app/                     # Next.js App Router
│   │   ├── layout.tsx           # 根布局：AppShell（顶部导航 + 侧边栏 + 主内容区）
│   │   ├── page.tsx             # / → redirect to /jobs
│   │   ├── globals.css          # Tailwind 指令 + CSS 变量（设计 token）
│   │   ├── jobs/
│   │   │   └── page.tsx         # 岗位总览页
│   │   ├── match/
│   │   │   └── page.tsx         # 智能匹配页
│   │   ├── compare/
│   │   │   └── page.tsx         # 岗位对比页
│   │   └── settings/
│   │       └── page.tsx         # 设置页
│   ├── components/
│   │   ├── layout/              # 布局组件
│   │   │   ├── AppShell.tsx     # 整体布局壳（TopNav + Sidebar + 内容区）
│   │   │   ├── TopNav.tsx       # 顶部导航栏（Logo + 全局搜索框）
│   │   │   ├── Sidebar.tsx      # 左侧导航菜单
│   │   │   └── PageContainer.tsx # 页面内容容器（统一 padding / max-width）
│   │   ├── jobs/                # 岗位相关业务组件
│   │   │   ├── CompanySelector.tsx   # 公司选择器（复用于总览/匹配/对比页）
│   │   │   ├── FilterBar.tsx         # 筛选区（方向/地点/类型/时间）
│   │   │   ├── FilterTag.tsx         # 已选筛选标签（带 × 关闭）
│   │   │   ├── JobCard.tsx           # 岗位卡片
│   │   │   ├── JobCardGrid.tsx       # 卡片网格容器
│   │   │   ├── JobDetailPanel.tsx    # 右侧滑出详情面板（基于 shadcn Sheet）
│   │   │   └── SortControl.tsx       # 排序选择 + 总数显示
│   │   ├── report/              # 报告相关业务组件
│   │   │   ├── AnalysisPageLayout.tsx # 匹配/对比页共享布局
│   │   │   ├── ResumeUploader.tsx    # 简历拖拽上传
│   │   │   ├── PreferencesForm.tsx   # 偏好填写表单
│   │   │   ├── ReportRenderer.tsx    # 流式报告 Markdown 渲染
│   │   │   ├── ReportCard.tsx        # 报告中的单个岗位推荐卡
│   │   │   └── GenerateButton.tsx    # 生成报告按钮（含 loading 态）
│   │   ├── chat/                # 对话相关（基于 assistant-ui）
│   │   │   ├── ChatPanel.tsx         # 封装 assistant-ui Thread 组件
│   │   │   └── ChatProvider.tsx      # assistant-ui RuntimeProvider 配置
│   │   ├── search/              # 搜索相关
│   │   │   ├── GlobalSearch.tsx      # 顶部全局搜索框
│   │   │   └── SearchSuggestions.tsx  # 自动补全下拉（基于 shadcn Popover）
│   │   └── ui/                  # shadcn/ui 组件（按需 add 安装）
│   │       ├── button.tsx
│   │       ├── select.tsx
│   │       ├── badge.tsx
│   │       ├── input.tsx
│   │       ├── textarea.tsx
│   │       ├── sheet.tsx        # 用于侧滑面板
│   │       ├── separator.tsx
│   │       ├── skeleton.tsx     # 骨架屏加载态
│   │       ├── popover.tsx      # 搜索补全下拉
│   │       ├── dropdown-menu.tsx
│   │       ├── tooltip.tsx
│   │       ├── alert-dialog.tsx # 简历覆盖确认弹窗
│   │       └── ...
│   ├── lib/                     # 工具层
│   │   ├── api/                 # API 调用层
│   │   │   ├── client.ts        # fetch 封装（拦截器、信封解包、错误处理）
│   │   │   ├── companies.ts
│   │   │   ├── jobs.ts
│   │   │   ├── favorites.ts
│   │   │   ├── resume.ts
│   │   │   ├── match.ts
│   │   │   ├── compare.ts
│   │   │   ├── chat.ts
│   │   │   ├── crawl.ts
│   │   │   └── settings.ts
│   │   ├── sse.ts               # SSE 流式消费工具函数
│   │   ├── upload.ts            # 文件上传工具函数
│   │   └── utils.ts             # 通用工具（cn(), formatDate(), etc.）
│   ├── hooks/                   # 自定义 React Hooks
│   │   ├── useJobs.ts           # 岗位列表查询 + 筛选
│   │   ├── useFavorites.ts      # 收藏操作
│   │   ├── useResume.ts         # 简历状态
│   │   ├── useSSE.ts            # SSE 流式消费 Hook
│   │   ├── useReport.ts         # 报告生成 + 加载
│   │   ├── useChat.ts           # 追问对话
│   │   └── useDebounce.ts       # 搜索防抖
│   ├── store/                   # Zustand 状态管理
│   │   ├── useCompanyStore.ts   # 当前选中公司
│   │   ├── useFavoriteStore.ts  # 收藏状态（乐观更新）
│   │   ├── useResumeStore.ts    # 简历上传状态
│   │   └── useSettingsStore.ts  # 显示偏好
│   └── types/                   # TypeScript 类型定义
│       ├── api.ts               # ApiResponse 信封、PaginationMeta
│       ├── job.ts
│       ├── company.ts
│       ├── favorite.ts
│       ├── resume.ts
│       ├── report.ts
│       ├── chat.ts
│       └── crawl.ts
└── tests/
```

---

## 2. 路由设计

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | — | redirect → `/jobs` |
| `/jobs` | 岗位总览 | 公司选择 + 筛选 + 卡片列表 + 详情侧滑面板 |
| `/match` | 智能匹配 | 选公司 + 上传简历 + 偏好 + 报告 + 追问对话 |
| `/compare` | 岗位对比 | 选公司 + 上传简历 + 偏好 + 报告 + 追问对话 |
| `/settings` | 设置 | 显示偏好 + 目标公司管理（增删改 + 手动触发爬取 + 状态展示） |

4 个页面，所有页面共享 `AppShell` 布局（TopNav + Sidebar），无嵌套路由。

搜索不单独开路由——在 `/jobs` 页通过 URL query param `?search=React` 驱动搜索结果展示。

---

## 3. 状态管理

### 3.1 选型：Zustand

**选型理由：**

| 对比维度 | Zustand | Redux Toolkit | Jotai / Context |
|----------|---------|---------------|-----------------|
| 样板代码 | 极少 | 较多 | 少 |
| 学习曲线 | 低 | 中 | 低 |
| DevTools | 支持 | 支持 | 有限 |
| 与 Next.js App Router 兼容 | 好（无 Provider 要求） | 需 Provider 包裹 | Context 有 SSR 陷阱 |
| 体积 | ~1KB | ~12KB | ~3KB |

本项目全局状态少（当前公司、收藏集合、简历状态、设置偏好），Zustand 的 store-per-concern 模式匹配度高。

### 3.2 Store 定义

```typescript
// store/useCompanyStore.ts
interface CompanyStore {
  companies: Company[]           // 公司列表（从 API 加载）
  selectedId: string | null      // 当前选中的公司 ID
  setSelected: (id: string) => void
  fetchCompanies: () => Promise<void>
}

// store/useFavoriteStore.ts
interface FavoriteStore {
  favoriteIds: Set<string>       // 收藏岗位 ID 集合（O(1) 查找）
  summary: FavoriteSummary[]     // 各公司收藏数量概要
  toggle: (jobId: string) => void // 切换收藏（乐观更新 + API 调用）
  fetchFavorites: () => Promise<void>
  fetchSummary: () => Promise<void>
}

// store/useResumeStore.ts
interface ResumeStore {
  resume: ResumeInfo | null      // 当前简历信息
  isUploading: boolean           // 上传中状态
  upload: (file: File) => Promise<void>  // 上传后刷新状态
  fetchResume: () => Promise<void>
  deleteResume: () => Promise<void>
}

// store/useSettingsStore.ts
interface SettingsStore {
  density: 'comfortable' | 'compact'
  language: 'zh' | 'en'
  update: (patch: Partial<Settings>) => Promise<void>
  fetchSettings: () => Promise<void>
}
```

### 3.3 状态分层原则

| 状态类型 | 存放位置 | 生命周期 |
|----------|----------|----------|
| 公司列表、收藏集合、简历状态、设置偏好 | Zustand store | 全局，跨页面共享 |
| 报告内容（Markdown）、流式状态 | `useReport` hook + 页面 state | 页面级，离开释放 |
| 对话历史、流式回复 | `useChat` hook + assistant-ui | 页面级，离开释放 |
| 筛选条件、排序、分页 | URL query params + 页面 state | 页面级 |

---

## 4. API 调用层

### 4.1 设计原则

前端 API 层**不包含任何 mock 逻辑**。前端始终通过 `NEXT_PUBLIC_API_BASE_URL` 调用后端 API，开发阶段通过切换该地址指向 mock server 或真实后端，前端代码零改动。

```
开发阶段：前端 → Mock Server (localhost:3001)     ← Express.js 伪后端
联调阶段：前端 → 真实后端   (localhost:8000)      ← FastAPI
```

### 4.2 API 客户端

```typescript
// lib/api/client.ts
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3001'

export async function apiGet<T>(path: string, params?: Record<string, string>): Promise<ApiResponse<T>> {
  const url = new URL(`${API_BASE}${path}`)
  if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))
  const res = await fetch(url.toString())
  if (!res.ok) {
    const body = await res.json()
    throw new ApiError(body.error.code, body.error.message, res.status)
  }
  return res.json()
}

export async function apiPost<T>(path: string, body?: unknown): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const errBody = await res.json()
    throw new ApiError(errBody.error.code, errBody.error.message, res.status)
  }
  return res.json()
}

export async function apiDelete<T>(path: string): Promise<ApiResponse<T>> { /* 同上模式 */ }

export async function apiPatch<T>(path: string, body?: unknown): Promise<ApiResponse<T>> { /* 同上模式 */ }
```

> 注意：默认 `API_BASE` 指向 `localhost:3001`（mock server），联调时改为 `localhost:8000`（真实后端）。

### 4.3 每个模块的 API 函数

```typescript
// lib/api/companies.ts
export const fetchCompanies = () => apiGet<Company[]>('/api/companies')
export const createCompany = (data: CompanyCreate) => apiPost<Company>('/api/companies', data)
export const updateCompany = (id: string, data: CompanyUpdate) => apiPut<Company>(`/api/companies/${id}`, data)
export const deleteCompany = (id: string) => apiDelete<null>(`/api/companies/${id}`)

// lib/api/jobs.ts
export const fetchJobs = (params: JobQueryParams) => apiGet<Job[]>('/api/jobs', params)
export const fetchJob = (id: string) => apiGet<Job>(`/api/jobs/${id}`)
export const searchJobs = (params: SearchParams) => apiGet<Job[]>('/api/jobs/search', params)
export const fetchSuggestions = (q: string) => apiGet<string[]>('/api/jobs/suggest', { q })

// lib/api/favorites.ts
export const addFavorite = (jobId: string) => apiPost<{job_id: string}>('/api/favorites', { job_id: jobId })
export const removeFavorite = (jobId: string) => apiDelete(`/api/favorites/${jobId}`)
export const fetchFavorites = (companyId?: string) => apiGet<FavoriteItem[]>('/api/favorites', companyId ? { company_id: companyId } : undefined)
export const fetchFavoritesSummary = () => apiGet<FavoriteSummary[]>('/api/favorites/summary')

// lib/api/resume.ts
export const uploadResume = (file: File) => uploadFile<ResumeUploadResponse>('/api/resume/upload', file)
export const fetchResume = () => apiGet<ResumeInfo | null>('/api/resume')
export const deleteResume = () => apiDelete('/api/resume')

// lib/api/match.ts
export const generateMatchReport = (body: GenerateRequest) => streamSSE('/api/match/generate', body)
export const fetchMatchReport = (companyId: string) => apiGet<Report | null>('/api/match/report', { company_id: companyId })

// lib/api/compare.ts
export const generateCompareReport = (body: GenerateRequest) => streamSSE('/api/compare/generate', body)
export const fetchCompareReport = (companyId: string) => apiGet<Report | null>('/api/compare/report', { company_id: companyId })

// lib/api/chat.ts
export const sendChatMessage = (body: ChatRequest) => streamSSE('/api/chat/message', body)
export const fetchChatHistory = (reportId: string) => apiGet<ChatHistory>('/api/chat/history', { report_id: reportId })

// lib/api/settings.ts
export const fetchSettings = () => apiGet<Settings>('/api/settings')
export const updateSettings = (patch: Partial<Settings>) => apiPatch<Settings>('/api/settings', patch)
```

---

## 4A. Mock Server（独立模块）

Mock Server 是一个独立的 Express.js 项目，完整实现 API 规范中定义的所有接口（含 SSE 流式接口和文件上传），返回假数据。前端开发阶段直接对接 mock server，无需等待真实后端就绪。

### 4A.1 目录结构

```
mock-server/
├── package.json
├── tsconfig.json
├── src/
│   ├── index.ts                  # Express 入口，挂载路由 + CORS + 端口监听
│   ├── routes/                   # 路由（与真实后端 API 路径一一对应）
│   │   ├── companies.ts          # GET /api/companies
│   │   ├── jobs.ts               # GET /api/jobs, /api/jobs/:id, /search, /suggest
│   │   ├── favorites.ts          # POST/DELETE/GET /api/favorites
│   │   ├── resume.ts             # POST/GET/DELETE /api/resume
│   │   ├── match.ts              # POST /api/match/generate (SSE), GET /api/match/report
│   │   ├── compare.ts            # POST /api/compare/generate (SSE), GET /api/compare/report
│   │   ├── chat.ts               # POST /api/chat/message (SSE), GET /api/chat/history
│   │   ├── crawl.ts              # POST /api/crawl/trigger, GET /api/crawl/tasks
│   │   └── settings.ts           # GET/PATCH /api/settings
│   ├── data/                     # 静态 mock 数据
│   │   ├── companies.json
│   │   ├── jobs.json             # 包含多家公司的完整岗位列表
│   │   ├── report-match.md       # 匹配报告 Markdown 模板
│   │   ├── report-compare.md     # 对比报告 Markdown 模板
│   │   └── chat-responses.json   # 预设的对话回复
│   ├── store.ts                  # 内存状态管理（收藏、简历、报告、设置）
│   └── helpers/
│       ├── response.ts           # 统一响应信封包装
│       ├── pagination.ts         # 分页计算
│       └── sse.ts                # SSE 流式发送辅助函数
└── README.md
```

### 4A.2 核心实现

```typescript
// src/index.ts
import express from 'express'
import cors from 'cors'
import { companiesRouter } from './routes/companies'
import { jobsRouter } from './routes/jobs'
import { favoritesRouter } from './routes/favorites'
import { resumeRouter } from './routes/resume'
import { matchRouter } from './routes/match'
import { compareRouter } from './routes/compare'
import { chatRouter } from './routes/chat'
import { crawlRouter } from './routes/crawl'
import { settingsRouter } from './routes/settings'

const app = express()
app.use(cors())
app.use(express.json())

app.use('/api', companiesRouter)
app.use('/api', jobsRouter)
app.use('/api', favoritesRouter)
app.use('/api', resumeRouter)
app.use('/api', matchRouter)
app.use('/api', compareRouter)
app.use('/api', chatRouter)
app.use('/api', crawlRouter)
app.use('/api', settingsRouter)

app.listen(3001, () => console.log('Mock server running on http://localhost:3001'))
```

```typescript
// src/store.ts — 内存状态（模拟数据库）
import jobs from './data/jobs.json'

export const store = {
  favorites: new Set<string>(),           // 收藏的岗位 ID
  resume: null as ResumeData | null,      // 当前简历
  reports: new Map<string, ReportData>(), // key = `${company_id}_${type}`
  chatHistory: new Map<string, Message[]>(), // key = report_id
  settings: { display_density: 'comfortable', language: 'zh' },
}
```

```typescript
// src/helpers/sse.ts — SSE 流式发送
export async function sendSSE(
  res: Response,
  startEvent: string,
  endEvent: string,
  markdownContent: string,
  reportId: string,
  jobIds: string[]
) {
  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Connection', 'keep-alive')

  // 发送 start 事件
  res.write(`event: ${startEvent}\ndata: ${JSON.stringify({ report_id: reportId })}\n\n`)

  // 逐段发送 chunk（模拟流式生成）
  const chunks = markdownContent.split('\n\n')
  for (const chunk of chunks) {
    await new Promise(r => setTimeout(r, 100))  // 100ms 延迟模拟
    res.write(`event: chunk\ndata: ${JSON.stringify({ content: chunk + '\n\n' })}\n\n`)
  }

  // 发送 end 事件
  res.write(`event: ${endEvent}\ndata: ${JSON.stringify({ report_id: reportId, job_ids: jobIds })}\n\n`)
  res.end()
}
```

```typescript
// src/helpers/response.ts — 统一信封包装
export function ok<T>(data: T, pagination?: PaginationMeta) {
  return {
    success: true,
    data,
    error: null,
    pagination: pagination ?? null,
  }
}

export function err(code: string, message: string, status: number) {
  return {
    success: false,
    data: null,
    error: { code, message },
    pagination: null,
  }
}
```

### 4A.3 关键路由示例

```typescript
// src/routes/jobs.ts
import { Router } from 'express'
import jobsData from '../data/jobs.json'
import { ok } from '../helpers/response'
import { paginate } from '../helpers/pagination'

const router = Router()

router.get('/jobs', (req, res) => {
  let jobs = jobsData
  const { company_id, category, location, job_type, posted_within, page, page_size } = req.query

  // 筛选
  if (company_id) jobs = jobs.filter(j => j.company.id === company_id)
  if (category) {
    const cats = (category as string).split(',')
    jobs = jobs.filter(j => cats.includes(j.category))
  }
  if (location) jobs = jobs.filter(j => j.location === location)
  if (job_type) jobs = jobs.filter(j => j.job_type === job_type)

  // 分页
  const { data, pagination } = paginate(jobs, Number(page) || 1, Number(page_size) || 20)

  // 注入 is_favorited
  const withFav = data.map(j => ({ ...j, is_favorited: store.favorites.has(j.id) }))

  res.json(ok(withFav, pagination))
})

// POST /api/match/generate — SSE 流式
router.post('/match/generate', async (req, res) => {
  const { company_id } = req.body
  const reportMd = fs.readFileSync('./src/data/report-match.md', 'utf-8')
  const reportId = randomUUID()
  const jobIds = jobsData.filter(j => j.company.id === company_id).slice(0, 3).map(j => j.id)

  // 存入内存
  store.reports.set(`${company_id}_match`, { id: reportId, content: reportMd, jobIds })

  await sendSSE(res, 'report_start', 'report_end', reportMd, reportId, jobIds)
})

export { router as jobsRouter }
```

### 4A.4 Mock Server 有状态行为

Mock Server 在内存中维护状态，模拟真实后端的业务逻辑：

| 行为 | 实现 |
|------|------|
| 收藏/取消收藏 | `store.favorites` Set 增删，`GET /api/jobs` 返回时注入 `is_favorited` |
| 上传简历 | 接收 multipart（使用 `multer`），存入 `store.resume`，清空 `store.reports` 和 `store.chatHistory` |
| 生成报告 | SSE 流式发送预设 Markdown，同时存入 `store.reports` |
| 追问对话 | SSE 流式发送预设回复，追加到 `store.chatHistory` |
| 重新生成报告 | 清空该公司对应报告 + 对话历史，重新 SSE 发送 |
| 设置更新 | 修改 `store.settings` 内存值 |

### 4A.5 依赖清单

```json
{
  "dependencies": {
    "express": "^4",
    "cors": "^2",
    "multer": "^1",
    "uuid": "^9"
  },
  "devDependencies": {
    "typescript": "^5",
    "tsx": "^4",
    "@types/express": "^4",
    "@types/cors": "^2",
    "@types/multer": "^1"
  }
}
```

### 4A.6 启动方式

```bash
cd mock-server
bun install
bun run dev          # tsx watch src/index.ts → localhost:3001
```

---

## 5. SSE 流式消费方案

### 5.1 底层工具函数

```typescript
// lib/sse.ts
export interface SSEEvent {
  event: string
  data: any
}

export async function* consumeSSE(url: string, body: unknown): AsyncGenerator<SSEEvent> {
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3001'
  const res = await fetch(`${API_BASE}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const errBody = await res.json()
    throw new ApiError(errBody.error.code, errBody.error.message, res.status)
  }

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // 按 SSE 协议分割：空行（\n\n）分隔事件
    const parts = buffer.split('\n\n')
    buffer = parts.pop()! // 最后一段可能不完整
    for (const part of parts) {
      const event = parseSSEEvent(part)
      if (event) yield event
    }
  }
}

function parseSSEEvent(raw: string): SSEEvent | null {
  let event = 'message'
  let data = ''
  for (const line of raw.split('\n')) {
    if (line.startsWith('event: ')) event = line.slice(7)
    else if (line.startsWith('data: ')) data += line.slice(6)
  }
  if (!data) return null
  return { event, data: JSON.parse(data) }
}
```

### 5.2 React Hook

```typescript
// hooks/useSSE.ts
export function useSSE() {
  const [content, setContent] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [reportId, setReportId] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const start = useCallback(async (url: string, body: unknown) => {
    setContent('')
    setIsStreaming(true)
    setReportId(null)

    try {
      for await (const event of consumeSSE(url, body)) {
        switch (event.event) {
          case 'report_start':
          case 'compare_start':
          case 'chat_start':
            setReportId(event.data.report_id || event.data.message_id)
            break
          case 'chunk':
            setContent(prev => prev + event.data.content)
            break
          case 'report_end':
          case 'compare_end':
          case 'chat_end':
            // 流式完成
            break
        }
      }
    } finally {
      setIsStreaming(false)
    }
  }, [])

  const stop = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return { content, isStreaming, reportId, start, stop }
}
```

> 报告生成（match/compare）和追问对话（chat）复用同一套 `useSSE`，仅传入不同的 URL 和请求体。

---

## 6. 文件上传方案

```typescript
// lib/upload.ts
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3001'

export async function uploadFile<T>(path: string, file: File): Promise<ApiResponse<T>> {
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    body: formData,  // 不手动设 Content-Type，浏览器自动加 boundary
  })

  if (!res.ok) {
    const errBody = await res.json()
    throw new ApiError(errBody.error.code, errBody.error.message, res.status)
  }

  return res.json()
}
```

---

## 7. 关键共享组件

| 组件 | 来源 | 复用场景 | 核心 Props |
|------|------|----------|-----------|
| `CompanySelector` | 自定义 | 总览页、匹配页、对比页 | `value`, `onChange`, `showFavoriteCount?` |
| `ResumeUploader` | 自定义 | 匹配页、对比页 | `onUploadSuccess`, `currentResume` |
| `PreferencesForm` | 自定义 | 匹配页、对比页 | `onSubmit`, `submitLabel` |
| `ReportRenderer` | 自定义 | 匹配页、对比页 | `content`, `isStreaming`, `onJobClick` |
| `ChatPanel` | assistant-ui 封装 | 匹配页、对比页 | `reportId` |
| `AnalysisPageLayout` | 自定义 | 匹配页、对比页 | `title`, `description`, `apiEndpoint`, `reportType` |
| `JobDetailPanel` | 自定义 (shadcn Sheet) | 总览页、报告中点击岗位 | `jobId`, `open`, `onClose` |
| `GlobalSearch` | 自定义 (shadcn Input + Popover) | TopNav | — |
| `FilterBar` | 自定义 (shadcn Select) | 总览页 | `filters`, `onChange` |
| Button, Select, Badge, Sheet, etc. | shadcn/ui | 全局 | shadcn 标准 props |
| Thread, Composer, AssistantMessage | assistant-ui | ChatPanel 内部 | assistant-ui 标准 props |

### AnalysisPageLayout

智能匹配和岗位对比页面结构高度相似，提取共享布局组件：

```typescript
// components/report/AnalysisPageLayout.tsx
interface AnalysisPageLayoutProps {
  title: string                     // "智能匹配" | "岗位对比"
  description: string               // 页面描述文案
  generateEndpoint: string          // "/api/match/generate" | "/api/compare/generate"
  reportEndpoint: string            // "/api/match/report" | "/api/compare/report"
  generateButtonLabel: string       // "生成推荐报告" | "生成对比报告"
}

// 内部结构：
// ① CompanySelector（显示收藏数）
// ② ResumeUploader
// ③ PreferencesForm + GenerateButton
// ④ ReportRenderer（流式渲染）
// ⑤ ChatPanel（报告生成后显示）
```

---

## 8. assistant-ui 对接

### ChatProvider 配置

```typescript
// components/chat/ChatProvider.tsx
import { AssistantRuntimeProvider, useExternalStoreRuntime } from '@assistant-ui/react'

// 使用 useExternalStoreRuntime 对接自定义后端 SSE 接口
// 而非 AI SDK 的标准 useChat，因为后端是自定义 SSE 协议

export function ChatProvider({ reportId, children }) {
  // 1. 从 API 加载历史消息 GET /api/chat/history?report_id=xxx
  // 2. 发送新消息时调用 POST /api/chat/message（SSE 流式）
  // 3. 将 SSE chunks 映射为 assistant-ui 的消息格式
  // 4. 流式完成后持久化到本地消息列表

  const runtime = useExternalStoreRuntime({
    messages,              // 消息列表
    isRunning,             // 是否正在流式回复
    onNew: async (msg) => {
      // 调用 SSE 接口，逐 chunk 更新 messages
    },
  })

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  )
}
```

### ChatPanel 封装

```typescript
// components/chat/ChatPanel.tsx
import { Thread } from '@assistant-ui/react'

export function ChatPanel({ reportId }: { reportId: string }) {
  return (
    <ChatProvider reportId={reportId}>
      <Thread />
    </ChatProvider>
  )
}
```

assistant-ui 提供的组件：
- `Thread` — 完整对话线程（消息列表 + Composer 输入框 + 流式渲染）
- `AssistantMessage` / `UserMessage` — 消息气泡（内置 Markdown 渲染）
- `Composer` — 输入框 + 发送按钮

---

## 9. 关键依赖清单

```json
{
  "dependencies": {
    "next": "latest",
    "react": "latest",
    "react-dom": "latest",
    "tailwindcss": "latest",
    "@assistant-ui/react": "latest",
    "zustand": "latest",
    "lucide-react": "latest",
    "react-markdown": "latest",
    "remark-gfm": "latest",
    "clsx": "latest",
    "tailwind-merge": "latest",
    "class-variance-authority": "latest"
  }
}
```

> shadcn/ui 不是 npm 包依赖——通过 `npx shadcn@latest add <component>` 按需安装到 `src/components/ui/`。

---

## 10. 环境变量

```env
# .env.local（开发阶段 — 对接 mock server）
NEXT_PUBLIC_API_BASE_URL=http://localhost:3001
```

```env
# .env.local（联调阶段 — 对接真实后端，切换时只改这一行）
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

```env
# .env.example
NEXT_PUBLIC_API_BASE_URL=http://localhost:3001
```

### 开发流程

```bash
# 终端 1：启动 mock server
cd mock-server && bun run dev        # → localhost:3001

# 终端 2：启动前端
cd frontend && bun run dev           # → localhost:3000，API 请求指向 3001

# 联调时：改 .env.local 为 localhost:8000，重启前端即可
```
