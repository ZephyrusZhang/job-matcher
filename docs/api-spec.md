# API 规范文档

> 智能岗位聚合与匹配平台 — RESTful API 完整规范
>
> 本文档是前后端并行开发的唯一契约。所有接口均以 `/api` 为前缀。

---

## 统一响应信封

所有接口（除 SSE 流式接口外）统一使用以下 JSON 信封格式：

```json
// 成功响应
{
  "success": true,
  "data": "<T>",
  "error": null,
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}

// 错误响应
{
  "success": false,
  "data": null,
  "error": {
    "code": "NOT_FOUND",
    "message": "岗位不存在",
    "details": {}
  },
  "pagination": null
}
```

- `pagination` 仅在分页接口中存在，非分页接口为 `null`。
- `error.code` 为机器可读的错误码，`error.message` 为人可读的描述。

## 分页方案：Offset-based

选型理由：岗位列表数据量中等（单公司几十到几百条），无需实时一致性保证，Offset 分页实现简单、前端无状态管理负担，且支持"跳转到第 N 页"。

---

## 状态码约定

| 状态码 | 场景 |
|--------|------|
| `200` | 成功 |
| `201` | 创建成功 |
| `400` | 请求参数错误 |
| `404` | 资源不存在 |
| `409` | 资源冲突（如爬取任务正在进行中） |
| `413` | 文件过大 |
| `415` | 不支持的文件格式 |
| `422` | 业务逻辑错误（如无收藏岗位时发起匹配、未上传简历时生成报告） |
| `500` | 服务端错误 |

---

## 模块 1：公司列表（只读）

公司信息来源于后端 YAML 配置文件，前端仅可读取。

### GET /api/companies

获取所有目标公司列表。

**Request:** 无参数

**Response 200:**

```json
{
  "success": true,
  "data": [
    {
      "id": "bytedance",
      "name": "字节跳动",
      "career_url": "https://jobs.bytedance.com/...",
      "crawl_interval_hours": 12,
      "last_crawled_at": "2026-03-29T10:00:00Z",
      "job_count": 42
    },
    {
      "id": "meituan",
      "name": "美团",
      "career_url": "https://zhaopin.meituan.com/...",
      "crawl_interval_hours": 24,
      "last_crawled_at": "2026-03-29T05:00:00Z",
      "job_count": 28
    }
  ],
  "error": null,
  "pagination": null
}
```

**Response Schema — Company:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `string` | 公司唯一标识（YAML 中定义） |
| `name` | `string` | 公司中文名称 |
| `career_url` | `string` | 招聘页 URL |
| `crawl_interval_hours` | `int` | 采集频率（小时） |
| `last_crawled_at` | `string \| null` | 最近一次采集时间（ISO 8601），未采集过为 `null` |
| `job_count` | `int` | 该公司已采集的岗位数量 |

---

## 模块 2：岗位浏览

### GET /api/jobs

获取岗位列表（分页 + 筛选）。

**Query Parameters:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `company_id` | `string` | 是 | — | 按公司筛选 |
| `category` | `string` | 否 | — | 岗位方向，多选用逗号分隔（如 `后端,前端`） |
| `location` | `string` | 否 | — | 工作地点 |
| `job_type` | `string` | 否 | — | 岗位类型：`fulltime` / `intern` / `parttime` / `contract` |
| `posted_within` | `string` | 否 | — | 发布时间范围：`24h` / `7d` / `30d` |
| `sort_by` | `string` | 否 | `posted_date` | 排序字段：`posted_date` / `title` |
| `sort_order` | `string` | 否 | `desc` | 排序方向：`desc` / `asc` |
| `page` | `int` | 否 | `1` | 页码 |
| `page_size` | `int` | 否 | `20` | 每页数量（最大 50） |

**Response 200:**

```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "前端开发工程师",
      "category": "前端",
      "company": {
        "id": "bytedance",
        "name": "字节跳动"
      },
      "location": "北京",
      "job_type": "fulltime",
      "responsibilities": "负责抖音前端界面的开发与性能优化...",
      "requirements": {
        "must_have": ["React", "TypeScript"],
        "nice_to_have": ["GraphQL", "Webpack"]
      },
      "department": "抖音前端团队",
      "department_product": "抖音",
      "education": "本科及以上",
      "experience": "2年以上",
      "posted_date": "2026-03-27",
      "source_url": "https://jobs.bytedance.com/position/123",
      "summary": "负责抖音前端界面的开发与性能优化工作",
      "is_favorited": true,
      "created_at": "2026-03-27T10:00:00Z"
    }
  ],
  "error": null,
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 42,
    "total_pages": 3
  }
}
```

**Response Schema — Job:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `string` | 岗位 UUID |
| `title` | `string` | 岗位名称 |
| `category` | `string` | 岗位方向（算法/后端/前端/...） |
| `company` | `object` | `{ id: string, name: string }` |
| `location` | `string \| null` | 工作地点 |
| `job_type` | `string \| null` | 岗位类型 |
| `responsibilities` | `string` | 核心职责 |
| `requirements` | `object` | `{ must_have: string[], nice_to_have: string[] }` |
| `department` | `string \| null` | 所属部门 |
| `department_product` | `string \| null` | 部门产品 |
| `education` | `string \| null` | 学历要求 |
| `experience` | `string \| null` | 经验要求 |
| `posted_date` | `string \| null` | 发布日期（ISO date） |
| `source_url` | `string` | 原始链接 |
| `summary` | `string \| null` | 一句话概述 |
| `is_favorited` | `boolean` | 当前是否已收藏 |
| `created_at` | `string` | 入库时间 |

---

### GET /api/jobs/{job_id}

获取单个岗位详情。

**Path Parameters:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `job_id` | `string` | 岗位 UUID |

**Response 200:** `data` 为单个 Job 对象（Schema 同上）。

**Response 404:** 岗位不存在。

---

### GET /api/jobs/search

关键词搜索岗位。搜索范围覆盖岗位名称、职责描述、技术要求等全部字段。

**Query Parameters:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `q` | `string` | 是 | — | 搜索关键词 |
| `company_id` | `string` | 否 | — | 限定搜索范围到某公司 |
| `page` | `int` | 否 | `1` | 页码 |
| `page_size` | `int` | 否 | `20` | 每页数量 |

**Response 200:** 同 `GET /api/jobs`，返回匹配的岗位列表（含分页）。

---

### GET /api/jobs/suggest

搜索自动补全，返回建议关键词。

**Query Parameters:**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `q` | `string` | 是 | — | 输入前缀 |
| `limit` | `int` | 否 | `5` | 返回建议数量 |

**Response 200:**

```json
{
  "success": true,
  "data": ["React", "React Native", "Real-time Systems"],
  "error": null,
  "pagination": null
}
```

---

## 模块 3：收藏管理

### POST /api/favorites

收藏岗位。

**Request Body:**

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `job_id` | `string` | 是 | 岗位 UUID |

**Response 201:**

```json
{
  "success": true,
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "favorited_at": "2026-03-29T08:00:00Z"
  },
  "error": null,
  "pagination": null
}
```

**Response 404:** 岗位不存在。

---

### DELETE /api/favorites/{job_id}

取消收藏。

**Path Parameters:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `job_id` | `string` | 岗位 UUID |

**Response 200:**

```json
{
  "success": true,
  "data": null,
  "error": null,
  "pagination": null
}
```

---

### GET /api/favorites

获取收藏的岗位列表。

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `company_id` | `string` | 否 | 按公司筛选（不传则返回全部） |

**Response 200:**

```json
{
  "success": true,
  "data": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "前端开发工程师",
      "category": "前端",
      "company_name": "字节跳动",
      "location": "北京",
      "favorited_at": "2026-03-29T08:00:00Z"
    }
  ],
  "error": null,
  "pagination": null
}
```

---

### GET /api/favorites/summary

获取收藏概要（各公司收藏数量）。

**Response 200:**

```json
{
  "success": true,
  "data": [
    { "company_id": "bytedance", "company_name": "字节跳动", "count": 5 },
    { "company_id": "meituan", "company_name": "美团", "count": 4 }
  ],
  "error": null,
  "pagination": null
}
```

---

## 模块 4：简历管理（单例）

系统全局仅存储一份简历。上传新简历会覆盖旧简历，并**清空所有已生成的报告和对话历史**。

### POST /api/resume/upload

上传 / 覆盖简历。

**Request:** `Content-Type: multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | `File` | 是 | PDF 或 DOCX 文件，最大 10MB |

**Response 200:**

```json
{
  "success": true,
  "data": {
    "filename": "resume_2026.pdf",
    "parsed": {
      "skills": ["React", "TypeScript", "Python"],
      "experience_years": 1,
      "education": "本科 计算机科学",
      "raw_text": "..."
    },
    "uploaded_at": "2026-03-29T08:00:00Z",
    "cleared": {
      "reports_deleted": 3,
      "messages_deleted": 12
    }
  },
  "error": null,
  "pagination": null
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `filename` | `string` | 上传的文件名 |
| `parsed.skills` | `string[]` | LLM 提取的技能列表 |
| `parsed.experience_years` | `int \| null` | 工作经验年限 |
| `parsed.education` | `string \| null` | 教育背景 |
| `parsed.raw_text` | `string` | 提取的纯文本内容 |
| `uploaded_at` | `string` | 上传时间 |
| `cleared.reports_deleted` | `int` | 本次上传清空的报告数 |
| `cleared.messages_deleted` | `int` | 本次上传清空的对话消息数 |

**Response 413:** 文件过大。

**Response 415:** 不支持的文件格式。

---

### GET /api/resume

获取当前简历信息。

**Response 200:**

```json
{
  "success": true,
  "data": {
    "filename": "resume_2026.pdf",
    "parsed": {
      "skills": ["React", "TypeScript", "Python"],
      "experience_years": 1,
      "education": "本科 计算机科学",
      "raw_text": "..."
    },
    "uploaded_at": "2026-03-29T08:00:00Z"
  },
  "error": null,
  "pagination": null
}
```

> 未上传简历时 `data` 为 `null`。

---

### DELETE /api/resume

删除简历。同时清空所有报告和对话历史。

**Response 200:**

```json
{
  "success": true,
  "data": {
    "cleared": {
      "reports_deleted": 3,
      "messages_deleted": 12
    }
  },
  "error": null,
  "pagination": null
}
```

---

## 模块 5：智能匹配

### POST /api/match/generate

生成推荐报告（SSE 流式）。后端自动使用当前唯一简历。

如果该公司已有旧的匹配报告，会先清空旧报告及其关联的对话历史，再生成新报告。

**Request Body:**

```json
{
  "company_id": "bytedance",
  "preferences": {
    "interest": "对前端开发方向最感兴趣，也愿意尝试全栈方向",
    "additional": "希望有远程或混合办公选项，偏好有导师制度的团队"
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `company_id` | `string` | 是 | 目标公司 ID |
| `preferences.interest` | `string` | 是 | 岗位兴趣方向 |
| `preferences.additional` | `string` | 否 | 其他要求或补充说明 |

**Response: SSE `text/event-stream`**

```
event: report_start
data: {"report_id": "a1b2c3d4-..."}

event: chunk
data: {"content": "🏅 推荐 #1  前端开发工程师\n\n📌 推荐理由\n..."}

event: chunk
data: {"content": "（续）...你的 React 和 TypeScript 技能与该岗位核心要求高度契合..."}

event: report_end
data: {"report_id": "a1b2c3d4-...", "job_ids": ["uuid1", "uuid2", "uuid3"]}
```

| SSE Event | data 字段 | 说明 |
|-----------|-----------|------|
| `report_start` | `report_id: string` | 报告 ID，后续用于追问对话 |
| `chunk` | `content: string` | Markdown 文本片段，前端追加渲染 |
| `report_end` | `report_id: string, job_ids: string[]` | 报告完成，关联的岗位 ID 列表 |

**Error 422:** 未上传简历（`RESUME_NOT_FOUND`）或该公司无收藏岗位（`NO_FAVORITES`）。

---

### GET /api/match/report

获取某公司的推荐报告（每公司最多一份）。

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `company_id` | `string` | 是 | 目标公司 ID |

**Response 200:**

```json
{
  "success": true,
  "data": {
    "report_id": "a1b2c3d4-...",
    "company_id": "bytedance",
    "content": "🏅 推荐 #1  前端开发工程师\n\n📌 推荐理由\n...",
    "job_ids": ["uuid1", "uuid2", "uuid3"],
    "preferences": {
      "interest": "对前端开发方向最感兴趣",
      "additional": "希望有远程办公选项"
    },
    "created_at": "2026-03-29T10:00:00Z"
  },
  "error": null,
  "pagination": null
}
```

> 未生成过则 `data` 为 `null`。

---

## 模块 6：岗位对比

### POST /api/compare/generate

生成对比报告（SSE 流式）。逻辑同智能匹配，报告内容为横向对比分析。

如果该公司已有旧的对比报告，会先清空旧报告及其关联的对话历史，再生成新报告。

**Request Body:**

```json
{
  "company_id": "bytedance",
  "preferences": {
    "interest": "希望做全栈方向，能接触前后端都可以",
    "additional": "更看重技术成长而非薪资，希望团队有 code review 文化"
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `company_id` | `string` | 是 | 目标公司 ID |
| `preferences.interest` | `string` | 是 | 岗位兴趣方向 |
| `preferences.additional` | `string` | 否 | 其他要求或补充说明 |

**Response: SSE `text/event-stream`**

```
event: compare_start
data: {"report_id": "e5f6g7h8-..."}

event: chunk
data: {"content": "🏅 推荐 #1  全栈开发实习生\n\n📌 推荐理由\n..."}

event: chunk
data: {"content": "（续）...最符合你"全栈方向"的偏好..."}

event: compare_end
data: {"report_id": "e5f6g7h8-...", "job_ids": ["uuid1", "uuid2"]}
```

| SSE Event | data 字段 | 说明 |
|-----------|-----------|------|
| `compare_start` | `report_id: string` | 报告 ID |
| `chunk` | `content: string` | Markdown 文本片段 |
| `compare_end` | `report_id: string, job_ids: string[]` | 报告完成 |

**Error 422:** 同智能匹配。

---

### GET /api/compare/report

获取某公司的对比报告（每公司最多一份）。

**Query Parameters / Response:** 同 `GET /api/match/report`。

---

## 模块 7：追问对话

### POST /api/chat/message

发送追问消息（SSE 流式）。后端自动携带简历、偏好、报告内容和对话历史作为 LLM 上下文。

**Request Body:**

```json
{
  "report_id": "a1b2c3d4-...",
  "message": "推荐 #1 的前端岗位，面试一般会考什么？"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `report_id` | `string` | 是 | 关联的报告 ID（match 或 compare） |
| `message` | `string` | 是 | 用户追问内容 |

**Response: SSE `text/event-stream`**

```
event: chat_start
data: {"message_id": "m1n2o3p4-..."}

event: chunk
data: {"content": "根据该岗位的技术要求（React + TypeScript），面试通常会涉及以下方面：\n\n"}

event: chunk
data: {"content": "• React 组件设计与性能优化（如 memo、useMemo）\n"}

event: chat_end
data: {"message_id": "m1n2o3p4-..."}
```

| SSE Event | data 字段 | 说明 |
|-----------|-----------|------|
| `chat_start` | `message_id: string` | 本条回复的消息 ID |
| `chunk` | `content: string` | 文本片段 |
| `chat_end` | `message_id: string` | 回复完成 |

**Error 404:** 报告不存在。

---

### GET /api/chat/history

获取某报告的对话历史。

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `report_id` | `string` | 是 | 关联的报告 ID |

**Response 200:**

```json
{
  "success": true,
  "data": {
    "report_id": "a1b2c3d4-...",
    "messages": [
      {
        "id": "m1n2o3p4-...",
        "role": "user",
        "content": "推荐 #1 面试一般考什么？",
        "created_at": "2026-03-29T10:05:00Z"
      },
      {
        "id": "m5n6o7p8-...",
        "role": "assistant",
        "content": "根据该岗位的技术要求...",
        "created_at": "2026-03-29T10:05:03Z"
      }
    ]
  },
  "error": null,
  "pagination": null
}
```

---

## 模块 8：爬虫任务管理

### POST /api/crawl/trigger

手动触发某公司的爬取任务。

**Request Body:**

```json
{
  "company_id": "bytedance"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `company_id` | `string` | 是 | 目标公司 ID |

**Response 201:**

```json
{
  "success": true,
  "data": {
    "task_id": "t1a2s3k4-...",
    "company_id": "bytedance",
    "status": "pending",
    "created_at": "2026-03-29T10:00:00Z"
  },
  "error": null,
  "pagination": null
}
```

**Error 409:** 该公司已有正在进行的爬取任务（`CRAWL_IN_PROGRESS`）。

---

### GET /api/crawl/tasks

获取爬取任务列表。

**Query Parameters:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `company_id` | `string` | 否 | 按公司筛选 |
| `page` | `int` | 否 | 页码，默认 1 |
| `page_size` | `int` | 否 | 每页数量，默认 20 |

**Response 200:**

```json
{
  "success": true,
  "data": [
    {
      "id": "t1a2s3k4-...",
      "company_id": "bytedance",
      "company_name": "字节跳动",
      "status": "completed",
      "jobs_found": 15,
      "jobs_new": 3,
      "jobs_updated": 2,
      "error_message": null,
      "started_at": "2026-03-29T10:00:00Z",
      "completed_at": "2026-03-29T10:02:30Z",
      "created_at": "2026-03-29T10:00:00Z"
    }
  ],
  "error": null,
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 5,
    "total_pages": 1
  }
}
```

**Response Schema — CrawlTask:**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `string` | 任务 UUID |
| `company_id` | `string` | 公司 ID |
| `company_name` | `string` | 公司名称 |
| `status` | `string` | `pending` / `running` / `completed` / `failed` |
| `jobs_found` | `int` | 发现的岗位总数 |
| `jobs_new` | `int` | 新增岗位数 |
| `jobs_updated` | `int` | 更新岗位数 |
| `error_message` | `string \| null` | 错误信息（仅 failed 状态） |
| `started_at` | `string \| null` | 开始时间 |
| `completed_at` | `string \| null` | 完成时间 |
| `created_at` | `string` | 创建时间 |

---

### GET /api/crawl/tasks/{task_id}

获取单个任务详情。

**Response 200:** `data` 为单个 CrawlTask 对象。

**Response 404:** 任务不存在。

---

## 模块 9：设置

### GET /api/settings

获取用户显示偏好设置。

**Response 200:**

```json
{
  "success": true,
  "data": {
    "display_density": "comfortable",
    "language": "zh"
  },
  "error": null,
  "pagination": null
}
```

---

### PATCH /api/settings

更新显示偏好。

**Request Body:**

```json
{
  "display_density": "compact",
  "language": "zh"
}
```

| 字段 | 类型 | 必填 | 可选值 | 说明 |
|------|------|------|--------|------|
| `display_density` | `string` | 否 | `comfortable` / `compact` | 信息密度 |
| `language` | `string` | 否 | `zh` / `en` | 界面语言 |

**Response 200:**

```json
{
  "success": true,
  "data": {
    "display_density": "compact",
    "language": "zh"
  },
  "error": null,
  "pagination": null
}
```

---

## 清空级联关系

| 触发动作 | 清空范围 |
|----------|----------|
| 上传新简历 | **所有**报告 + **所有**对话历史 |
| 删除简历 | **所有**报告 + **所有**对话历史 |
| 重新生成某公司匹配报告 | 该公司旧匹配报告 + 其对话历史 |
| 重新生成某公司对比报告 | 该公司旧对比报告 + 其对话历史 |
