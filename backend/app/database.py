import aiosqlite
from pathlib import Path

from app.config import DatabaseConfig

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id                 TEXT PRIMARY KEY,
    company_id         TEXT NOT NULL,
    title              TEXT NOT NULL,
    category           TEXT NOT NULL,
    location           TEXT,
    job_type           TEXT,
    responsibilities   TEXT,
    requirements_must  TEXT,
    requirements_nice  TEXT,
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

INSERT OR IGNORE INTO settings (id, display_density, language) VALUES (1, 'comfortable', 'zh');
"""


async def init_database(config: DatabaseConfig) -> None:
    """Create tables if they don't exist."""
    db_path = Path(config.path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.executescript(_CREATE_TABLES_SQL)
        await db.commit()


async def get_db(db_path: str) -> aiosqlite.Connection:
    """Get a database connection with foreign keys enabled."""
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db
