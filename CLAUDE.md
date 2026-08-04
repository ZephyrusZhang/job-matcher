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

Tables are created by `_CREATE_TABLES_SQL` in `app/database.py` — there is no migration framework, so schema changes mean editing that DDL plus a hand-written script in `backend/scripts/`. Several columns hold JSON-encoded text: `jobs.location` is a JSON array (filtering uses `LIKE '%"城市"%'`), `requirements_must`/`requirements_nice` are JSON arrays, `reports.job_ids`/`preferences` are JSON. `reports` has `UNIQUE(company_id, report_type)`, so a regenerated report replaces the old one.

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
4. On success the generated script is persisted to the `crawler_scripts` table. Subsequent crawls for that company take the fast path `run_cached_crawler()` and skip the LLM entirely — the settings page exposes CRUD on that script via `/api/companies/{id}/crawler-script` (Monaco editor).
5. `pipeline.py::store_jobs` normalizes raw output: `category.py` / `job_type.py` / `location.py` map free-form site values onto the fixed taxonomies, falling back to batched LLM classification (32 jobs per call) whose results persist to `backend/data/category_cache.json`. Dedup is by `(source_url, company_id)`; `content_hash` is computed but not currently used for update detection.

`CrawlService` schedules crawls as asyncio tasks on the main loop, capped at 2 concurrent by `_crawl_semaphore`, with a per-task `threading.Event` for cancellation. Cancellation is cooperative — checked between graph nodes and between job inserts. The crawl task ID doubles as the LangGraph `thread_id`, so each crawl's agent conversation is checkpointed and can be inspected or resumed.

The legacy console + JSONL event stream is preserved: `app/crawl/callbacks.py::CrawlEventBridge` translates LangChain callbacks back into the original `AgentEvent` objects, so `ConsoleHandler` output and `logs/agent_<ts>.jsonl` keep their exact schema. `CrawlerAgent.compact_history` overrides the framework's default token-based trimming because dropping a message would orphan its tool results — it compresses old tool payloads in place instead, matching the original `maybe_compress_history`.

### Streaming (SSE)

`/api/match/generate`, `/api/compare/generate`, and `/api/chat/message` return `StreamingResponse` with `X-Accel-Buffering: no`. The wire format is hand-rolled in `services/report_service.py` / `chat_service.py`:

```
event: report_start | compare_start   data: {"report_id": ...}
event: chat_start                     data: {"message_id": ...}     # note the different key
event: chunk                          data: {"content": "..."}
event: report_end | compare_end       data: {"report_id": ..., "job_ids": [...]}
event: chat_end                       data: {"message_id": ...}
```

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
