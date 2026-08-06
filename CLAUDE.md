# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

Three independent packages, no monorepo tooling:

- `backend/` — FastAPI + aiosqlite service (uv-managed). Contains the crawl Agent.
- `frontend/` — Next.js 16 App Router app (Bun-managed).
- `mock-server/` — legacy Express stub of the API on port 3001, untouched since the real backend landed. Do not extend it; only useful for frontend-only work.

## Commands

```bash
# Backend (run from backend/)
uv sync                                           # runtime deps only
uv sync --extra dev                               # adds pytest — required before running tests
uv run playwright install chromium                # local browser for the crawl agent
uv run uvicorn app.main:app --reload --port 3001  # dev server (frontend defaults to :3001)
uv run pytest                                     # all tests
uv run pytest tests/test_models.py::test_name -v  # single test

# Frontend (run from frontend/)
bun install
bun dev
bun run build
bun run lint                                      # eslint (no `test` script defined)
bunx vitest run                                   # vitest is configured but no test files exist yet
bunx vitest run src/path/to/File.test.tsx         # single file

# Crawl sandbox image — must exist before any crawl runs
docker build -f backend/Dockerfile.sandbox -t crawler-sandbox backend/

# Agent framework store — must be running before any agent (incl. crawls) runs
docker-compose up -d agent-db
```

Host port 5432 is already occupied on this machine, so set `POSTGRES_PORT` (e.g. `5433`) in `backend/.env` and start the container with the same value. Inside Docker the backend always reaches Postgres on 5432.

Ports are inconsistent by design: `config/settings.yml` defaults to 8000 (what Docker uses), while local dev runs on 3001 to match `NEXT_PUBLIC_API_BASE_URL`'s fallback in `frontend/src/lib/api/client.ts`.

## Backend architecture

### Request flow

`routers/` → `services/` → `models/` (raw SQL) → SQLite. `schemas/` holds Pydantic request/response models. Two invariants worth knowing:

- **Every JSON response is the `ApiResponse` envelope** (`schemas/common.py`): `{success, data, error, pagination}`. Routers return `ApiResponse.ok(...)`; the global handlers in `main.py` produce the same shape for errors. The frontend's `lib/api/client.ts` unwraps it and throws `ApiError`.
- **Errors are raised as `AppError` subclasses** (`exceptions.py`), each carrying a stable machine code + Chinese message + HTTP status. Never raise bare `HTTPException`; add a subclass instead.

### Service wiring

Services are module-level singletons created once in `dependencies.py::init_services()`, called from the FastAPI lifespan. They hold no DB connection — a fresh `aiosqlite` connection is yielded per request by `get_database()`. `CompanyService` additionally holds an in-memory `_cache` of the companies table, loaded once at startup and hand-maintained by its own `create`/`update`/`delete`; any new write path that touches `companies` must keep that dict in sync or lookups like `has_company` will go stale.

### Configuration

`config/settings.yml` is loaded and `${ENV_VAR}` placeholders are recursively substituted from `backend/.env` (`app/config.py`). Relative `database.path` / `uploads.dir` are re-anchored to `backend/` in the lifespan. `config/companies.yml` is *seed data only* — it is inserted once when the `companies` table is empty; after that the DB is authoritative.

### Schema notes

Tables are created by `_CREATE_TABLES_SQL` in `app/database.py` — there is no migration framework, so schema changes mean editing that DDL plus a hand-written script in `backend/scripts/`. Several columns hold JSON-encoded text: `jobs.location` is a JSON array (filtering uses `LIKE '%"城市"%'`), `reports.job_ids`/`preferences` are JSON. `reports` has `UNIQUE(company_id, report_type)`, so a regenerated report replaces the old one.

A posting's prose is exactly two plain-text columns, `jobs.description` (职位描述) and `jobs.requirements` (职位要求), both the careers site's own text with its newlines intact — no arrays, no HTML. They replaced a seven-column split (`responsibilities`, `requirements_must`, `requirements_nice`, `department`, `department_product`, `education`, `experience`, plus `summary`) that asked crawlers to separate prose careers sites do not separate: six of those columns were NULL on all 1946 rows. When a site publishes one undivided block, it goes in `description` and `requirements` stays empty — `scripts/migrate_job_description.py` converts an old database, and `normalize_job`/`prebatch_classify` still read the old `responsibilities` key so pre-migration cached crawler scripts keep working.

`resumes` replaced the old singleton `resume` table (migration: `scripts/migrate_multi_resume.py`); exactly one row carries `is_default`, which is what `GET /api/resume` returns for `/compare`.

Categories, job types, and locations are stored in **Chinese** (`前端`, `实习`, `北京`), not the English names shown in the README.

### Agent framework (`app/core/`, `app/agents/`)

Ported from the `fastapi-langgraph-agent-production-ready-template`. Defining a new agent means subclassing `BaseAgent` in `app/agents/`, declaring `name`/`tools`/`build_system_prompt`, and calling `register()`. Stateful conversations, long-term memory, tool calling, tracing, metrics, retries and cancellation are all inherited.

**Two configuration systems coexist, deliberately.** `app/config.py` loads business config from `config/settings.yml`; `app/core/config.py` loads framework config (`settings`) from environment variables. They do not overlap — but note the framework reuses the existing `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` variables, so there is only one set of LLM credentials.

**Two databases, likewise.** Business data (jobs, favorites, reports, crawl tasks) stays in SQLite via `app/database.py` and `app/models/`. The agent framework owns a separate Postgres+pgvector instance holding the LangGraph checkpoint tables, mem0's vector collection, and the `user`/`session` auth tables (`app/core/db/`). Nothing was migrated between them.

Key constraint: **the LangGraph checkpointer pool is bound to the event loop that opened it**, so agents must run on the main loop. That is why agent tools wrap blocking work in `asyncio.to_thread` instead of whole agents running in worker threads — and why `CrawlService` now schedules crawls with `asyncio.create_task` + a semaphore rather than a `ThreadPoolExecutor`.

Optional and off by default: `LONG_TERM_MEMORY_ENABLED` (mem0 needs an embeddings endpoint, which DeepSeek does not expose), `LANGFUSE_TRACING_ENABLED`, and `AUTH_ENABLED`. The auth router at `/api/v1/auth` is only mounted when `AUTH_ENABLED=true`; business endpoints never require a token either way. Rate limiting applies only to routes with an explicit `@limiter.limit()` decorator — no `SlowAPIMiddleware` is installed, so the settings page's 3-second `/api/companies` poll is unaffected.

### Crawl agent (`app/agents/crawler.py`, `app/crawl/`)

This is the most involved subsystem. It is a ReAct loop that *writes a crawler*, rather than a crawler itself:

1. `CrawlerAgent` runs up to 64 turns against the tools in `lc_tools.py`: `browser_open`, `browser_action`, `browser_screenshot`, `get_traffic`, `inspect_request`, `search_traffic`, `sandbox_write_file`, `sandbox_run_command`. These are LangChain wrappers over the same `browser_mgr`/`sandbox_mgr` singletons in `tools.py`, with names, descriptions and schemas unchanged from the pre-LangGraph implementation.
2. `browser.py` drives a local Playwright page and records every 200-JSON response; the agent inspects that traffic to find the site's real pagination/detail API (strategy is spelled out in `prompts.py`).
3. The agent writes `/home/user/crawler.py` into a **Docker sibling container** (`sandbox.py`, image `crawler-sandbox`, created via the mounted `/var/run/docker.sock`) and iterates until it produces `/home/user/output.json`.
4. On success the generated script is persisted to the `crawler_scripts` table — the settings page exposes CRUD on it via `/api/companies/{id}/crawler-script` (Monaco editor).

`POST /api/crawl/trigger` takes a `mode`, and the choice is honoured exactly: `agent` (the default) rewrites the crawler with the LLM and ignores any stored script, while `cached` runs `run_cached_crawler()` and **never escalates to the agent** — a failure marks the task failed instead. Picking the script implicitly, and silently falling back when it broke, is what made a stale crawler look like it still worked. The settings page asks which one via `components/settings/CrawlTriggerButton.tsx`; `CompanyOut.has_crawler_script` tells it whether the cached option is available at all.
5. `pipeline.py::store_jobs` normalizes raw output: `category.py` / `job_type.py` / `location.py` map free-form site values onto the fixed taxonomies, falling back to batched LLM classification (32 jobs per call) whose results persist to `backend/data/category_cache.json`. Dedup is by `(source_url, company_id)`; `content_hash` is computed but not currently used for update detection.

`CrawlService` schedules crawls as asyncio tasks on the main loop, capped at 2 concurrent by `_crawl_semaphore`, with a per-task `threading.Event` for cancellation. Cancellation is cooperative — checked between graph nodes and between job inserts. The crawl task ID doubles as the LangGraph `thread_id`, so each crawl's agent conversation is checkpointed and can be inspected or resumed.

The legacy console + JSONL event stream is preserved: `app/crawl/callbacks.py::CrawlEventBridge` translates LangChain callbacks back into the original `AgentEvent` objects, so `ConsoleHandler` output and `logs/agent_<ts>.jsonl` keep their exact schema. `CrawlerAgent.compact_history` overrides the framework's default token-based trimming because dropping a message would orphan its tool results — it compresses old tool payloads in place instead, matching the original `maybe_compress_history`.

### Match agent (`app/agents/matcher.py`)

`/match` is a chat page, not a report generator. `MatchAgent` recommends jobs from a scope the user picks in the composer (companies, multi-select, or favourites).

Two things make it different from the crawler:

- **`final_answer` is a terminal tool.** `BaseAgent.terminal_tools` routes to `END` when one is called, so the turn has an explicit exit. This separates the deliverable (`final_answer`'s payload, rendered as the message body) from narration (plain assistant text between tool calls, rendered muted). If the model answers in plain text instead, the service falls back to treating that as the answer; if it calls `final_answer` alongside other tools, the tool node defers it and answers the call with a "skipped" `ToolMessage` — a `tool_call` without a matching `ToolMessage` makes the next request fail.
- **`BaseAgent.streaming = True`.** `LLMService.call()` uses `ainvoke`, which issues a *non-streaming* request unless the model is built with `streaming=True`, and without it `on_llm_new_token` never fires. Since the final answer arrives as the `answer` argument of a tool call, `services/match_stream.py::FinalAnswerExtractor` decodes that partial JSON string incrementally (escapes and `\uXXXX` can straddle chunks). `MatchStreamBridge` pushes narration/tool/answer events onto an `asyncio.Queue` the SSE generator drains.

Scope is **not** a tool argument — `app/agents/match_tools.py` pins it in a `ContextVar` per turn, so the model cannot search outside what the user selected. Tools return compressed job views (~60 tokens each) because a scope can hold ~1000 jobs; full text comes from `get_job_detail` on demand.

### History compaction

`MatchAgent` overrides `compact_history` for the same reason `CrawlerAgent` does, and the failure it prevents is worth knowing. The framework default (`utils/graph.py::prepare_messages`) trims with `strategy="last"` and `start_on="human"`. A turn has exactly one human message — the question — at the very front, so once the accumulated tool results alone exceed the budget there is no human message left for the window to start on and `trim_messages` returns an **empty list**. The model then sees only the system prompt, greets the user mid-turn, and re-runs the tools it already ran until `max_turns` cuts it off with no answer. That is regression-tested in `tests/test_match_history.py`.

`max_history_tokens` on an agent is the **history budget**, not the reply length cap. The reply cap is `settings.MAX_TOKENS`, which `services/llm/registry.py` passes as the model's `max_tokens` — the same setting also serves as the *default* history budget in `prepare_messages`, so raising the env var changes both. Raise the agent attribute instead.

That budget is the point at which compaction *starts*, not a target size, so it belongs as close to the context window as is safe — a lower value only throws away context the model could still have used. `MatchAgent` derives it: `CONTEXT_WINDOW_TOKENS - settings.MAX_TOKENS - CONTEXT_RESERVE_TOKENS` (1M − 8k − 100k = 892k). The reserve covers the tool schemas, which the history count does not see, and the tokenizer gap — `count_tokens` uses cl100k_base because the provider's tokenizer is not in tiktoken.

### Embedded job cards

The answer cites jobs with `:job[<uuid>]` markers, which the frontend replaces with cards. A marker alone in its own paragraph becomes a block card; one inside a sentence becomes an inline chip — the distinction exists because a block card is a `<div>` and would be illegal inside the `<p>` a paragraph renders as.

`lib/remarkJobEmbed.ts` rewrites the markers in the **Markdown AST**, setting `data.hName` to `job-card` / `job-ref` / `job-card-group`; `mdast-util-to-hast` emits those tag names and `react-markdown` resolves them through its `components` map. Working on the AST (rather than string-replacing into raw HTML plus `rehype-raw`) means markers inside fenced or inline code are skipped for free, and no raw-HTML parsing is enabled on LLM output that carries crawled job descriptions. `types/jsx.d.ts` must declare each custom tag: without it `react-markdown`'s `Components` type silently accepts anything.

`app/utils/job_citations.py` parses the same markers server-side — it *does* have to strip code spans itself — and the result, filtered through `job_model.filter_existing`, becomes `match_messages.job_ids`. That column means "jobs this answer recommended"; it is stored as a record but nothing renders it. `TurnContext.cited_job_ids` is a different thing: every job the agent *looked at*, which one `search_jobs` call can fill with 40 rows.

Keep `JOB_RE` in `remarkJobEmbed.ts` and `_JOB_RE` in `job_citations.py` in sync. Both are pinned to the UUID shape, so a mis-transcribed id degrades to plain text instead of becoming a guaranteed 404.

### Resumable turns

A turn's lifetime belongs to `services/match_runs.py::registry`, not to any HTTP request — closing the tab drops a subscriber, not the run. `Run.emit` folds each frame, writes it to `match_messages`, *then* publishes it, so the stored `seq` is never behind what a client has seen and a reconnecting client can trust the row. `Run.attach` takes the snapshot and registers the queue under one lock, so the snapshot's `seq` and the first live frame are necessarily adjacent; that is why the client never sends an offset.

Two numbers are easy to confuse. `index` is *which step* a frame belongs to (hundreds of `narration` frames share one); `seq` is *which frame* it is. `match_messages.seq` is per-message, not session-global, so there is no `FirstSeq` equivalent.

`frontend/src/lib/matchAccumulator.ts` is a pure fold — every snapshot replaces it wholesale rather than merging, which is what makes replay safe. Never reintroduce `+=` on `finalAnswer` or narration in `useMatchChat`.

A subscription belongs to a **conversation**, not to the hook (`watchRef: {sessionId, controller}`). The sidebar switches conversations without unmounting, so a bare "is a stream alive" boolean both leaves the old stream running and blocks the new one — the visible symptom is a turn that freezes and then dumps its whole answer at the end.

When the model answers in plain text instead of calling `final_answer`, the **trailing** narration step is the answer. `MatchService._close_out` and `MatchTurnAccumulator.toState()` apply that same rule so the answer streams into the body live instead of hiding in the muted trace; only the trailing step, since earlier narration is interstitial and belongs to the trace.

Stopping goes through `BaseAgent.run`'s `cancel_check` (polled at graph node boundaries), not `Task.cancel()`. Because a turn can be cut between an `AIMessage` carrying `tool_calls` and its `ToolMessage` replies, `MatchService._repair_checkpoint` backfills placeholders — without it the *next* turn on that thread fails.

### Streaming (SSE)

`/api/compare/generate` and `/api/chat/message` return `StreamingResponse` with `X-Accel-Buffering: no`. The wire format is hand-rolled in `services/report_service.py` / `chat_service.py`:

```
event: compare_start                  data: {"report_id": ...}
event: chat_start                     data: {"message_id": ...}     # note the different key
event: chunk                          data: {"content": "..."}
event: compare_end                    data: {"report_id": ..., "job_ids": [...]}
event: chat_end                       data: {"message_id": ...}
```

`/match` does **not** stream from its submit endpoint. `POST /api/match/conversations/{id}/messages` records the turn, starts the agent and returns `{message_id}`; the answer is watched on `GET /api/match/conversations/{id}/stream`. Splitting them is what makes resume possible — a request carrying the question can never be retried, a subscription carrying only the id always can. See `docs/match-stream-resume-design.md`.

The subscription opens with `snapshot` (the turn's complete state, not a delta) and then streams `narration` / `tool_start` / `tool_args` / `tool_end` / `final_delta` / `message_end`, each frame carrying its `seq` as the SSE `id:`. `: ping` comments every 15s let the client detect a socket that died without closing.
`hooks/useSSE.ts` still serves `/compare` and was deliberately left alone.

`frontend/src/lib/sse.ts` parses this manually (POST + `ReadableStream`, not `EventSource`) and `hooks/useSSE.ts` maps the event names to state. Adding a new stream means touching both the emitter and that switch statement.

### Read-only demo mode

Two flags that must be set together: `READ_ONLY_MODE` (backend, `middleware/readonly.py` → 403 `READ_ONLY_MODE`) and `NEXT_PUBLIC_READ_ONLY_MODE` (frontend overlay, `lib/readonly.ts`). The middleware blocks `/api/match/*` and `/api/compare/*` entirely, plus write methods on settings/companies/crawl/resume. `NEXT_PUBLIC_*` is inlined at build time — it must be present during `bun run build`, not at runtime.

## Frontend architecture

`frontend/AGENTS.md` (aliased by `frontend/CLAUDE.md`) applies: **this is Next.js 16, newer than training data.** Read the relevant guide under `frontend/node_modules/next/dist/docs/` before writing App Router code. Use Bun, never npm/pnpm/npx.

- **Four pages**, all client components: `/jobs`, `/match`, `/compare`, `/settings`.
- **State split**: Zustand stores (`store/`) hold cross-page state — selected company, favorites, resume, settings — while `hooks/` hold per-page fetch state. `useFavoriteStore.toggle` updates optimistically and rolls back on failure.
- **All network calls go through `lib/api/*.ts`**, which wrap `apiGet/apiPost/apiPatch/apiDelete` from `lib/api/client.ts`. Components should not call `fetch` directly (SSE via `lib/sse.ts` is the exception).
- `components/ui/` is shadcn/Base UI primitives; `components/{jobs,report,layout,settings,common}/` is app code. Tailwind v4 (CSS-first config in `app/globals.css`), category/job-type colors centralized in `lib/constants.ts`.

## Design constraints

`.impeccable.md` is the binding visual spec for frontend work: dark-mode-first with full light support, macOS-like restraint, information density over decoration, hierarchy via spacing/weight/opacity rather than borders and shadows. Explicit anti-patterns: flashy gradients, cartoon icons, corporate blue-white, neon/cyberpunk.

## Commit convention

Conventional Commits plus a gitmoji, matching the existing history:

```
<type>(<scope>): <emoji> <lowercase description>
```

**Subject line only — no body.** Every commit in this repo is a single line; keep it that way. Scope is optional but used on nearly all commits.

| Type | Emoji | Used for |
|------|-------|----------|
| `feat` | ✨ `:sparkles:` | new capability |
| `fix` | 🐛 `:bug:` | bug fix |
| `refactor` | ♻️ `:recycle:` | behaviour-preserving restructure |
| `perf` | ⚡️ `:zap:` | performance |
| `docs` | 📝 `:memo:` | documentation |
| `style` | 💄 `:lipstick:` | visual/UI polish |
| `build` | 🐳 `:whale:` | Docker, deps, packaging |
| `chore` | 🔧 `:wrench:` | tooling/config |
| `chore(db)` | 🗃️ `:card_file_box:` | committing refreshed crawl data |

Scopes in use: `frontend`, `backend`, `crawler`, `crawl`, `db`, `scripts`, `vscode`.

Both literal emoji (`💄`) and gitmoji shortcodes (`:sparkles:`) appear in the history — either is fine, but the emoji always follows the colon and precedes the description.

Examples from the log:

```
feat(backend): ✨ crawler script caching with DB storage and auto-fallback
fix(crawler): :bug: fix category normalize when crawled field is `None`
refactor(crawl): ♻️ remove category normalization from agent, change output to {jobs:[...]}
perf(crawler): :zap: batched llm classify request
chore(db): :card_file_box: update `tencent` and `kuaishou` jobs
```

Note that `backend/data/job_matcher.db` and `backend/data/category_cache.json` are tracked, so refreshed crawl results are committed deliberately under `chore(db)` — keep those separate from code commits.

## Known drift

- **`tests/test_category.py` writes to the real `backend/data/category_cache.json`** — running the suite dirties a tracked data file. Check `git status` after running tests.
- **`backend/tests/conftest.py` is stale**: its `client` fixture calls `init_services(config)` with the old sync single-arg signature, so all 14 `test_api.py` tests error out; `test_config.py::test_load_config` also asserts a removed `AppConfig.companies` field. Fix the fixture rather than working around it.
- **`docs/backend-architecture.md` is a design doc, not a description of the code** — it documents `extractor.py`, `scheduler.py`, and `dedup.py`, none of which exist. The crawl agent replaced that plan. Trust the code; `docs/api-spec.md` is closer to accurate.
- There is no scheduler: `crawl_interval_hours` is stored but nothing acts on it; crawls are manually triggered from `/settings`.
