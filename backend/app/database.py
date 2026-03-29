"""SQLite database connection management and initialization."""

import aiosqlite

from app.config import DatabaseConfig

_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS jobs (
    id                 TEXT PRIMARY KEY,
    company_id         TEXT NOT NULL,
    title              TEXT NOT NULL,
    category           TEXT NOT NULL,
    location           TEXT,
    job_type           TEXT,
    responsibilities   TEXT,
    requirements      TEXT,
    department         TEXT,
    department_product TEXT,
    education          TEXT,
    experience         TEXT,
    posted_date        TEXT,
    source_url         TEXT NOT NULL,
    summary            TEXT,
    content_hash       TEXT NOT NULL,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_company      ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_category     ON jobs(category);
CREATE INDEX IF NOT EXISTS idx_jobs_location     ON jobs(location);
CREATE INDEX IF NOT EXISTS idx_jobs_job_type     ON jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_jobs_posted_date  ON jobs(posted_date DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_content_hash ON jobs(content_hash);

CREATE TABLE IF NOT EXISTS favorites (
    job_id     TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (job_id)
);

CREATE TABLE IF NOT EXISTS resume (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    filename    TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    parsed_data TEXT NOT NULL,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reports (
    id          TEXT PRIMARY KEY,
    company_id  TEXT NOT NULL,
    report_type TEXT NOT NULL,
    content     TEXT NOT NULL,
    job_ids     TEXT NOT NULL,
    preferences TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(company_id, report_type)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         TEXT PRIMARY KEY,
    report_id  TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chat_report ON chat_messages(report_id, created_at);

CREATE TABLE IF NOT EXISTS crawl_tasks (
    id            TEXT PRIMARY KEY,
    company_id    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    jobs_found    INTEGER DEFAULT 0,
    jobs_new      INTEGER DEFAULT 0,
    jobs_updated  INTEGER DEFAULT 0,
    error_message TEXT,
    started_at    TEXT,
    completed_at  TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_crawl_company ON crawl_tasks(company_id, created_at DESC);

CREATE TABLE IF NOT EXISTS settings (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    display_density TEXT NOT NULL DEFAULT 'comfortable',
    language        TEXT NOT NULL DEFAULT 'zh'
);

INSERT OR IGNORE INTO settings (id) VALUES (1);
"""


class Database:
    def __init__(self, config: DatabaseConfig):
        self._path = config.path
        self._conn: aiosqlite.Connection | None = None

    async def init(self):
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(_SCHEMA_SQL)
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        cursor = await self._conn.execute(sql, params)
        await self._conn.commit()
        return cursor

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        cursor = await self._conn.execute(sql, params)
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def execute_many(self, sql: str, params_list: list[tuple]):
        await self._conn.executemany(sql, params_list)
        await self._conn.commit()
