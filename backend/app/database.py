import aiosqlite
from pathlib import Path

import yaml

from app.config import DatabaseConfig

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS companies (
    id                   TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    career_url           TEXT NOT NULL,
    crawl_interval_hours INTEGER NOT NULL DEFAULT 12,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

-- A posting's prose is exactly two fields, both stored as the site's own text.
-- The earlier split (responsibilities / requirements_must / requirements_nice /
-- department / department_product / education / experience) asked crawlers to
-- classify prose that careers sites do not actually separate: 5 of those 7
-- columns were NULL for all 1946 rows, and the two that were populated were a
-- verbatim paragraph and that same paragraph split on newlines.
CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    company_id   TEXT NOT NULL,
    title        TEXT NOT NULL,
    category     TEXT NOT NULL,
    location     TEXT,
    job_type     TEXT,
    -- 职位描述: business line, team, what the job involves.
    description  TEXT,
    -- 职位要求: what is expected of the applicant.
    requirements TEXT,
    posted_date  TEXT,
    source_url   TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_company      ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_category     ON jobs(category);
CREATE INDEX IF NOT EXISTS idx_jobs_location     ON jobs(location);
CREATE INDEX IF NOT EXISTS idx_jobs_job_type     ON jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_jobs_posted_date  ON jobs(posted_date DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_content_hash ON jobs(content_hash);
CREATE INDEX IF NOT EXISTS idx_jobs_source_url   ON jobs(source_url, company_id);

CREATE TABLE IF NOT EXISTS favorites (
    job_id     TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (job_id)
);

CREATE TABLE IF NOT EXISTS resumes (
    id          TEXT PRIMARY KEY,
    filename    TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    parsed_data TEXT NOT NULL,
    label       TEXT NOT NULL DEFAULT '',
    is_default  INTEGER NOT NULL DEFAULT 0,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_resumes_default ON resumes(is_default DESC, uploaded_at DESC);

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

CREATE TABLE IF NOT EXISTS crawler_scripts (
    company_id  TEXT PRIMARY KEY,
    code        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Conversational job matching.
CREATE TABLE IF NOT EXISTS match_conversations (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_match_conv_updated ON match_conversations(updated_at DESC);

CREATE TABLE IF NOT EXISTS match_messages (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES match_conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT '',
    final_answer    TEXT,
    scope           TEXT,
    resume_id       TEXT,
    steps           TEXT,
    job_ids         TEXT,
    -- running | completed | stopped | failed | interrupted.
    -- A turn's row is inserted as `running` and updated frame by frame, so a
    -- client that reconnects mid-turn can pick the stream back up.
    status          TEXT NOT NULL DEFAULT 'completed',
    -- Frames folded into this row so far; the resume anchor. Monotonic within
    -- one assistant message, reset per turn.
    seq             INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_match_msg_session ON match_messages(session_id, created_at);

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
        await _seed_companies_from_yaml(db, db_path)


async def _seed_companies_from_yaml(
    db: aiosqlite.Connection, db_path: Path
) -> None:
    """One-time migration: seed companies from YAML if table is empty."""
    async with db.execute("SELECT COUNT(*) FROM companies") as cursor:
        count = (await cursor.fetchone())[0]
    if count > 0:
        return

    # Look for companies.yml relative to the db file
    config_dir = db_path.parent.parent / "config"
    yaml_path = config_dir / "companies.yml"
    if not yaml_path.exists():
        return

    with open(yaml_path) as f:
        data = yaml.safe_load(f) or {}

    for c in data.get("companies", []):
        await db.execute(
            """INSERT OR IGNORE INTO companies (id, name, career_url, crawl_interval_hours)
               VALUES (?, ?, ?, ?)""",
            (c["id"], c["name"], c["career_url"], c.get("crawl_interval_hours", 12)),
        )
    await db.commit()


async def get_db(db_path: str) -> aiosqlite.Connection:
    """Get a database connection with foreign keys enabled."""
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db
