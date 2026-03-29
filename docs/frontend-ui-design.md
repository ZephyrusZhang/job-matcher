# 前端 UI 设计草案

> 智能岗位聚合与匹配平台 — UI 设计规范
>
> 设计风格：参照 Claude 网页暗色主题，纯暗色模式，无亮色切换
>
> 组件库：shadcn/ui（通用组件）+ assistant-ui（对话组件）

---

## 1. 设计 Token

### 1.1 色彩

| Token | 色值 | 用途 |
|-------|------|------|
| `--bg-primary` | `#1a1a1a` | 页面主背景 |
| `--bg-secondary` | `#2a2a2a` | 卡片、面板、侧边栏背景 |
| `--bg-tertiary` | `#333333` | 输入框、筛选区、hover 态 |
| `--bg-elevated` | `#3a3a3a` | 弹出层、下拉菜单 |
| `--border` | `#3d3d3d` | 默认边框 |
| `--border-subtle` | `#2e2e2e` | 弱分隔线 |
| `--text-primary` | `#e8e4de` | 主文本（暖白色） |
| `--text-secondary` | `#a8a29e` | 次要文本、描述、时间戳 |
| `--text-muted` | `#6b6560` | 占位符、禁用态 |
| `--accent` | `#d4a27a` | 主强调色（暖橙/沙棕） |
| `--accent-hover` | `#e0b48f` | 强调色 hover |
| `--accent-muted` | `rgba(212,162,122,0.15)` | 强调色背景（选中态、收藏高亮） |
| `--red` | `#ef8a7a` | 必备技能标签、错误态 |
| `--red-bg` | `rgba(239,138,122,0.15)` | 必备技能标签背景 |
| `--blue` | `#7aafef` | 加分技能标签 |
| `--blue-bg` | `rgba(122,175,239,0.15)` | 加分技能标签背景 |
| `--green` | `#7aefa0` | 成功态（已上传、完成） |
| `--yellow` | `#efd97a` | 警告态 |

### 1.2 排版

| Token | 值 | 用途 |
|-------|-----|------|
| `--font-sans` | `'Inter', system-ui, sans-serif` | 全局字体 |
| `--text-xs` | `12px / 1.5` | 标签、时间戳、辅助文字 |
| `--text-sm` | `14px / 1.6` | 正文、卡片内容、列表项 |
| `--text-base` | `16px / 1.6` | 区块标题、输入框文字 |
| `--text-lg` | `20px / 1.4` | 页面副标题 |
| `--text-xl` | `24px / 1.3` | 页面主标题 |
| `--font-medium` | `500` | 标题、强调文字 |
| `--font-semibold` | `600` | Logo、关键操作 |

### 1.3 间距与圆角

| Token | 值 | 用途 |
|-------|-----|------|
| `--radius` | `12px` | 卡片、面板、大容器圆角 |
| `--radius-sm` | `8px` | 按钮、输入框、标签圆角 |
| `--radius-xs` | `4px` | 小标签、Badge 圆角 |
| `--spacing-page` | `24px` | 页面内边距 |
| `--spacing-card` | `16px` | 卡片内边距 |
| `--gap-grid` | `16px` | 卡片网格间距 |
| `--gap-section` | `24px` | 区块间距 |

### 1.4 通用规则

- 纯暗色模式，不实现亮色切换
- 不使用 box-shadow 做层级区分（Claude 风格：扁平、干净），统一用 `1px solid var(--border)` 做边界
- 所有交互元素 hover 过渡：`transition: all 150ms ease`
- 图标统一使用 lucide-react，尺寸默认 `16px`，配合文字时用 `inline` 对齐

---

## 2. 整体布局 — AppShell

```
┌─────────────────────────────────────────────────────────────────────┐
│ TopNav  h-14  bg-secondary  border-b                               │
│ ┌──────┐  ┌─────────────────────────────────────┐                  │
│ │ Logo │  │  🔍 搜索岗位...        (bg-tertiary) │                  │
│ └──────┘  └─────────────────────────────────────┘                  │
├────────┬────────────────────────────────────────────────────────────┤
│Sidebar │ Main Content Area                          bg-primary     │
│ w-56   │                                                           │
│bg-sec  │                                                           │
│border-r│                                                           │
│        │                                                           │
│ 📋 岗位│                                                           │
│   总览 │                  （根据左侧导航选择                        │
│        │                    展示对应页面内容）                       │
│ 🎯 智能│                                                           │
│   匹配 │                                                           │
│        │                                                           │
│ 📊 岗位│                                                           │
│   对比 │                                                           │
│        │                                                           │
│ ─────  │  ← Separator                                              │
│ ⚙️ 设置│                                                           │
│        │                                                           │
└────────┴────────────────────────────────────────────────────────────┘
```

### TopNav

- 高度 `h-14`（56px），`bg-secondary`，底部 `border-b`
- **左侧**：Logo 文字「JobMatcher」，`text-accent font-semibold text-base`
- **中间**：全局搜索框，lucide `Search` 图标前置，`bg-tertiary rounded-sm`，`placeholder="搜索岗位..."`
- 无右侧内容（本地运行，无用户信息）

### Sidebar

- 宽度 `w-56`（224px），`bg-secondary`，右侧 `border-r`
- 导航项样式：
  - 容器：`px-3 py-2 rounded-sm cursor-pointer`
  - 图标：lucide icon `16px`，与文字间距 `gap-3`
  - **选中态**：`bg-accent-muted text-accent`
  - **未选中**：`text-secondary`
  - **Hover**：`bg-tertiary text-primary`
- 设置项与上方菜单之间用 `Separator` 分隔

### 响应式布局

| 断点 | Sidebar | 卡片列数 | 详情面板 | 搜索框 |
|------|---------|----------|----------|--------|
| `≥1280px` | 常驻 `w-56` | 3 列 | `w-[480px]` Sheet | 展开 |
| `1024–1279px` | 常驻 `w-48` | 2 列 | `w-[480px]` Sheet | 展开 |
| `768–1023px` | 收起为 hamburger | 2 列 | `w-[480px]` Sheet | 展开 |
| `<768px` | hamburger + Sheet 展开 | 1 列 | 全屏 Sheet | 收起为图标 |

---

## 3. 岗位总览页 `/jobs`

### 3.1 页面结构

```
┌──────────────────────────────────────────────────────────────────┐
│ ① CompanySelector                                                │
│ ┌──────────────────────────────────────────┐                     │
│ │  🏢 字节跳动                          ▼  │  ← shadcn Select   │
│ └──────────────────────────────────────────┘                     │
│                                                                  │
│ ② FilterBar                                                     │
│ ┌──────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐               │
│ │ 岗位方向▼│ │ 地点 ▼ │ │ 岗位类型▼│ │ 发布时间▼│               │
│ └──────────┘ └────────┘ └──────────┘ └──────────┘               │
│ [后端 ×] [远程 ×]                      ← FilterTag pills        │
│                                                                  │
│ ③ SortControl                                                   │
│ 最新优先 ▼                                    共 42 个岗位      │
│                                                                  │
│ ④ JobCardGrid (响应式列数, gap-4)                                │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │
│ │  JobCard     │ │  JobCard     │ │  JobCard     │              │
│ └──────────────┘ └──────────────┘ └──────────────┘              │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │
│ │  JobCard     │ │  JobCard     │ │  JobCard     │              │
│ └──────────────┘ └──────────────┘ └──────────────┘              │
│                                                                  │
│                    [ 加载更多 ]  ← Button variant="outline"      │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 CompanySelector

- 基于 shadcn `Select` 组件
- 下拉选项显示公司名称 + 岗位数量：「字节跳动（42 个岗位）」
- 切换公司 → 重置所有筛选条件 → 回到第 1 页 → 重新请求

### 3.3 FilterBar

- 每个筛选器使用 shadcn `Select`
- **岗位方向**：支持多选，选项为 15 个预定义方向
- **地点 / 岗位类型 / 发布时间**：单选
- 选中的筛选项显示为 `FilterTag` pills（行内展示），点 `×` 移除
- FilterTag 样式：`bg-tertiary text-primary text-xs rounded-sm px-2 py-1`，右侧 `X` 图标
- 筛选变更 → 重置到第 1 页 → 请求

### 3.4 JobCard

```
┌─────────────────────────────────────────┐
│  bg-secondary  border  rounded          │
│  hover:border-accent  cursor-pointer    │
│  transition-colors                      │
│                                         │
│  ┌─ Header ───────────────────────────┐ │
│  │ 字节跳动         ⭐               │ │  ← 公司名 text-xs text-secondary
│  │                   (收藏按钮右上角) │ │     收藏: accent 填充 / 未收藏: secondary 描边
│  └────────────────────────────────────┘ │
│                                         │
│  前端开发工程师                         │  ← text-sm text-primary font-medium
│                                         │     line-clamp-2（最多两行）
│  📍 北京                               │  ← text-xs text-secondary, MapPin icon
│                                         │
│  ┌────┐ ┌────┐ ┌───┐                   │  ← 技术标签区域
│  │React│ │TS  │ │CSS│                   │     Badge: bg-tertiary text-primary text-xs
│  └────┘ └────┘ └───┘                   │     rounded-xs px-2 py-0.5
│                                         │     最多 4 个，超出显示 "+N"
│  🕐 2天前                              │  ← text-xs text-muted
└─────────────────────────────────────────┘
```

**交互：**
- 点击卡片主体 → 打开 JobDetailPanel
- 点击收藏按钮（⭐）→ 乐观更新收藏状态（不打开详情）
- Hover → `border-accent` 边框高亮

### 3.5 加载更多

- 按钮形式（非无限滚动），`Button variant="outline"` 居中
- 加载中：按钮内显示 `Spinner` + "加载中..."
- 无更多数据：按钮消失，显示 `text-muted text-sm` "已加载全部岗位"
- 首次加载：显示 6 个 `Skeleton` 卡片骨架屏

---

## 4. 岗位详情侧滑面板

```
┌──────────────────────────────┐┌──────────────────────────────────┐
│                              ││ Sheet side="right" w-[480px]     │
│                              ││ bg-secondary                     │
│     岗位总览页               ││                                  │
│     (背景 overlay 变暗)      ││ ┌─ Header ─────────────────────┐ │
│                              ││ │ 字节跳动    text-xs secondary│ │
│                              ││ │ 前端开发工程师  text-lg medium│ │
│                              ││ │ 📍北京 · 全职 · 混合办公     │ │
│                              ││ │        text-sm secondary     │ │
│                              ││ └─────────────────────────────┘ │
│                              ││                                  │
│                              ││ Separator                       │
│                              ││                                  │
│                              ││ ▎职位概述                       │
│                              ││ 一段话描述...                    │
│                              ││                                  │
│                              ││ ▎核心职责                       │
│                              ││ • 开发和维护搜索结果页面        │
│                              ││ • 优化页面加载性能              │
│                              ││ • 参与设计评审和代码审查        │
│                              ││                                  │
│                              ││ ▎技术要求                       │
│                              ││ 必备: [React] [TypeScript]      │
│                              ││ 加分: [GraphQL] [Webpack]       │
│                              ││                                  │
│                              ││ ▎团队与产品                     │
│                              ││ 部门: 抖音前端团队              │
│                              ││ 产品: 抖音                      │
│                              ││                                  │
│                              ││ Separator                       │
│                              ││ ┌─ Footer (sticky bottom) ───┐  │
│                              ││ │ [⭐ 收藏]   [🔗 原始链接]  │  │
│                              ││ └────────────────────────────┘  │
└──────────────────────────────┘└──────────────────────────────────┘
```

### 样式细节

- 使用 shadcn `Sheet` 组件，`side="right"`，宽度 `w-[480px]`
- 内容区可滚动 `overflow-y-auto`，Footer 固定在底部 `sticky bottom-0 bg-secondary`
- **Section 标题**：`text-accent text-sm font-medium`，左侧带 `2px solid accent` 竖线（`border-l-2 border-accent pl-3`）
- **Section 内容**：`text-sm text-primary leading-relaxed`
- **必备技能 Badge**：`bg-red-bg text-red border border-red/30 text-xs rounded-xs px-2 py-0.5`
- **加分技能 Badge**：`bg-blue-bg text-blue border border-blue/30 text-xs rounded-xs px-2 py-0.5`
- **收藏按钮**：
  - 已收藏：`bg-accent-muted text-accent border border-accent/30`
  - 未收藏：`variant="outline"`
- **原始链接按钮**：`variant="outline"`，点击 `window.open(url, '_blank')`

---

## 5. 智能匹配页 `/match` 与 岗位对比页 `/compare`

两个页面结构完全一致，共享 `AnalysisPageLayout` 布局组件，仅标题/描述文案/API endpoint 不同。

### 5.1 页面结构

```
┌──────────────────────────────────────────────────────────────────┐
│ ┌─ PageHeader ────────────────────────────────────────────────┐  │
│ │ 智能匹配                     text-xl font-medium           │  │
│ │ 从你收藏的岗位中，发现最适合你的岗位  text-sm text-secondary│  │
│ └─────────────────────────────────────────────────────────────┘  │
│                                                                  │
│ ┌─ InputSection  bg-secondary rounded border p-6 ─────────────┐ │
│ │                                                             │ │
│ │ ① 选择公司                                                 │ │
│ │ CompanySelector (带收藏数: "已收藏 5 个岗位")               │ │
│ │                                                             │ │
│ │ Separator                                                   │ │
│ │                                                             │ │
│ │ ② 上传简历                                                 │ │
│ │ ResumeUploader                                              │ │
│ │                                                             │ │
│ │ Separator                                                   │ │
│ │                                                             │ │
│ │ ③ 偏好与要求                                               │ │
│ │ PreferencesForm                                             │ │
│ │                                                             │ │
│ │              [ 🚀 生成推荐报告 ]                            │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ ┌─ ReportSection  bg-secondary rounded border p-6 ────────────┐ │
│ │ 推荐报告                       生成时间: 2026-03-29        │ │
│ │ Separator                                                   │ │
│ │ ReportRenderer (流式 Markdown 渲染)                         │ │
│ │   ├── ReportCard #1                                         │ │
│ │   ├── ReportCard #2                                         │ │
│ │   └── ReportCard #3                                         │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ ┌─ ChatSection  bg-secondary rounded border ──────────────────┐ │
│ │ assistant-ui <Thread>                                       │ │
│ │   ├── UserMessage                                           │ │
│ │   ├── AssistantMessage (流式渲染)                           │ │
│ │   └── Composer (输入框 + 发送)                              │ │
│ └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 CompanySelector（匹配/对比页变体）

- 与总览页共享组件，`showFavoriteCount={true}`
- 选项格式：「字节跳动（已收藏 5 个岗位）」
- 无收藏的公司显示为灰色禁用

### 5.3 ResumeUploader — 拖拽上传

```
默认态（未上传）:
┌─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐
│                                                                  │
│  📄 拖拽上传或点击选择文件                                        │
│  支持 PDF / DOCX，最大 10MB                                     │
│                                                                  │
│  border-dashed border-2 border-border rounded                    │
│  bg-transparent  text-secondary                                  │
│  "点击选择" 部分为 text-accent cursor-pointer                    │
└─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘

拖拽悬停态:
┌─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐
│                                                                  │
│  📄 松开以上传文件                                                │
│                                                                  │
│  border-accent bg-accent-muted  transition-all 150ms             │
└─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘

上传中:
┌──────────────────────────────────────────────────────────────────┐
│  ⏳ 上传中... resume_2026.pdf            Spinner + 文件名       │
└──────────────────────────────────────────────────────────────────┘

已上传:
┌──────────────────────────────────────────────────────────────────┐
│  ✅ resume_2026.pdf                              [重新上传]     │
│  技能: React, TypeScript, Python     text-xs text-muted         │
│                                                                  │
│  bg-secondary border rounded p-4                                 │
│  "重新上传" 为 text-accent text-sm cursor-pointer               │
└──────────────────────────────────────────────────────────────────┘
```

**重新上传交互：**
- 点击「重新上传」→ 弹出 shadcn `AlertDialog`
- 标题：「确认重新上传简历？」
- 描述：「上传新简历将清空所有已生成的报告和对话记录」
- 按钮：「取消」（outline）+「确认上传」（accent 背景）
- 确认后打开文件选择器

### 5.4 PreferencesForm

```
┌──────────────────────────────────────────────────────────────────┐
│  岗位兴趣方向:                      text-sm font-medium         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 对前端开发方向最感兴趣，也愿意尝试全栈方向...            │   │
│  │                                                          │   │
│  │ Textarea  bg-tertiary  rounded-sm  min-h-[80px]          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  其他要求或补充说明:              text-sm font-medium（可选）    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 希望有远程或混合办公选项...                               │   │
│  │                                                          │   │
│  │ Textarea  bg-tertiary  rounded-sm  min-h-[80px]          │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 5.5 GenerateButton

- 样式：`bg-accent text-bg-primary font-medium rounded-sm px-6 py-2`
- Hover：`bg-accent-hover`
- **Disabled 条件**（同时满足任一即禁用）：
  - 未选择公司
  - 未上传简历
  - 所选公司无收藏岗位
  - 正在生成中
- Disabled 样式：`opacity-50 cursor-not-allowed`
- 生成中：按钮文字变为 `Spinner` + "生成中..."，禁止重复点击

### 5.6 ReportRenderer — 流式报告渲染

- 使用 `react-markdown` + `remark-gfm` 实时渲染流式 Markdown
- 流式进行中：内容区底部显示打字光标 `▊`（`animate-pulse`）
- 流式完成后：光标消失

### 5.7 ReportCard — 报告中的岗位推荐卡

```
┌──────────────────────────────────────────────────────────────────┐
│  bg-primary rounded border p-5                                   │
│  （卡片用 bg-primary 背景，与外层 bg-secondary 形成层次）        │
│                                                                  │
│  ┌─ Header ──────────────────────────────────────────────────┐  │
│  │ 🏅 推荐 #1  前端开发工程师                    📍北京     │  │
│  │ text-base font-medium                text-sm secondary    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ▎推荐理由                  ← section-title 风格同详情面板      │
│  你的 React 和 TypeScript 技能与该岗位核心要求高度契合...       │
│  text-sm text-primary leading-relaxed                            │
│                                                                  │
│  ▎岗位前景                                                      │
│  抖音是字节跳动核心产品线...                                     │
│                                                                  │
│  ▎技术栈分析                                                    │
│  核心使用 React + TypeScript...                                  │
│                                                                  │
│  ▎潜在不足                                                      │
│  要求 2 年经验...                                                │
│                                                                  │
│                              查看岗位详情 →                      │
│                              text-accent text-sm hover:underline │
│                              点击 → 打开 JobDetailPanel          │
└──────────────────────────────────────────────────────────────────┘
```

> 对比报告额外包含「✅ 相对优势」和「⚠️ 相对不足」两个 section，末尾有「💡 综合建议」区块。

### 5.8 ChatSection — 追问对话

- 使用 assistant-ui 的 `Thread` 组件
- **UserMessage** 样式覆盖：`bg-tertiary rounded` 右对齐
- **AssistantMessage** 样式覆盖：`bg-transparent` 左对齐，内置 Markdown 渲染
- **Composer** 样式覆盖：`bg-tertiary rounded-sm`，发送按钮 `text-accent`
- 流式回复中：Composer 输入框禁用，显示 "正在回复..."
- **可见性**：报告未生成时 ChatSection 完全隐藏；报告流式完成后 ChatSection 渐入显示（`animate-in fade-in duration-300`）

### 5.9 智能匹配 vs 岗位对比 差异

| 维度 | 智能匹配 `/match` | 岗位对比 `/compare` |
|------|-------------------|---------------------|
| 页面标题 | "智能匹配" | "岗位对比" |
| 描述文案 | "从你收藏的岗位中，发现最适合你的岗位" | "对比你的意向岗位，找出最优选择" |
| 生成按钮 | "生成推荐报告" | "生成对比报告" |
| 报告标题 | "推荐报告" | "对比分析报告" |
| API endpoint | `/api/match/generate` | `/api/compare/generate` |
| 报告查询 | `/api/match/report` | `/api/compare/report` |
| 报告内容差异 | 无「相对优势/不足」 | 有「相对优势/不足」+ 综合建议 |

---

## 6. 设置页 `/settings`

```
┌──────────────────────────────────────────────────────────────────┐
│ 设置                              text-xl font-medium            │
│                                                                  │
│ ┌─ Card  bg-secondary rounded border p-6 ────────────────────┐  │
│ │ 显示偏好                     text-base font-medium          │  │
│ │ Separator  my-4                                             │  │
│ │                                                             │  │
│ │ 信息密度                     text-sm                        │  │
│ │ ○ 舒适    ● 紧凑            RadioGroup（shadcn）           │  │
│ │                                                             │  │
│ │ 语言                         text-sm                        │  │
│ │ [中文 ▼]                    Select（shadcn）                │  │
│ └─────────────────────────────────────────────────────────────┘  │
│                                                                  │
│ gap-section (24px)                                               │
│                                                                  │
│ ┌─ Card  bg-secondary rounded border p-6 ────────────────────┐  │
│ │ 目标公司                     text-base font-medium          │  │
│ │ Separator  my-4                                             │  │
│ │                                                             │  │
│ │ 以下公司的岗位将被自动采集   text-sm text-secondary         │  │
│ │                                                             │  │
│ │ ┌─ Table ──────────────────────────────────────────────┐   │  │
│ │ │ 公司名称         │ 采集频率    │ 上次采集            │   │  │
│ │ ├──────────────────┼────────────┼─────────────────────┤   │  │
│ │ │ 字节跳动         │ 每 12 小时 │ 2 小时前            │   │  │
│ │ │ 美团             │ 每 24 小时 │ 5 小时前            │   │  │
│ │ │ 阿里巴巴         │ 每 12 小时 │ 1 小时前            │   │  │
│ │ └──────────────────┴────────────┴─────────────────────┘   │  │
│ │                                                             │  │
│ │ text-sm  表格只读展示（数据来源于后端 YAML 配置）           │  │
│ └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

- 表格样式：无外边框，行间用 `border-b border-subtle`，表头 `text-secondary text-xs uppercase`
- 设置变更实时保存（`onChange` 即触发 API，无需保存按钮）

---

## 7. 全局搜索交互

```
TopNav 搜索框默认态:
┌────────────────────────────────────────────┐
│  🔍  搜索岗位...          bg-tertiary      │
└────────────────────────────────────────────┘

输入 + 自动补全:
┌────────────────────────────────────────────┐
│  🔍  Rea|                                  │
├────────────────────────────────────────────┤
│  Popover  bg-elevated  border  rounded     │
│                                            │
│  搜索建议               text-xs text-muted │
│  ┌──────────────────────────────────────┐  │
│  │ React               hover:bg-tertiary│  │
│  │ React Native                         │  │
│  │ Real-time Systems                    │  │
│  └──────────────────────────────────────┘  │
│                                            │
│  按 Enter 搜索全部结果   text-xs text-muted│
└────────────────────────────────────────────┘
```

- 使用 shadcn `Input` + `Popover` 组合
- 输入防抖 300ms 后请求 `/api/jobs/suggest`
- 点击建议项 → 跳转 `/jobs?search=React` 展示搜索结果
- 按 Enter → 跳转 `/jobs?search=当前输入` 展示搜索结果
- 搜索结果在岗位总览页内展示（复用 `JobCardGrid`），顶部显示 "搜索: React — 共 N 个结果"

---

## 8. 空状态设计

所有空状态统一使用 `EmptyState` 组件（居中布局，icon + 标题 + 描述 + 可选操作按钮）。

| 场景 | Icon | 标题 | 描述 | 操作 |
|------|------|------|------|------|
| 无岗位数据 | `Inbox` | 暂无岗位数据 | 请等待系统完成采集 | — |
| 无搜索结果 | `SearchX` | 未找到匹配的岗位 | 试试其他关键词 | — |
| 无收藏 | `Star` | 还没有收藏岗位 | 在总览页浏览并收藏感兴趣的岗位 | [前往总览] |
| 所选公司无收藏 | `Star` | 该公司还没有收藏岗位 | 先去总览页收藏一些岗位 | [前往总览] |
| 未上传简历 | — | — | — | ResumeUploader 默认态 |
| 未生成报告 | — | — | — | ReportSection 隐藏 |

EmptyState 样式：
- 容器：`flex flex-col items-center justify-center py-16`
- Icon：`text-muted w-12 h-12 mb-4`
- 标题：`text-primary text-base font-medium mb-2`
- 描述：`text-secondary text-sm mb-4`
- 按钮：`Button variant="outline" text-accent`

---

## 9. 加载态设计

| 场景 | 加载态 |
|------|--------|
| 岗位列表首次加载 | 6 个 `Skeleton` 卡片（与 JobCard 同尺寸） |
| 加载更多 | Button 内 `Spinner` + "加载中..." |
| 详情面板加载 | 面板内 `Skeleton` 行（模拟文本块） |
| 报告生成中 | 流式文字逐字出现 + 末尾 `▊` 光标闪烁 |
| 对话回复中 | assistant-ui 内置的流式渲染动画 |
| 简历上传中 | `Spinner` + 文件名 |
| 搜索建议加载 | Popover 内 3 行 `Skeleton` |

Skeleton 颜色：`bg-tertiary animate-pulse rounded`
