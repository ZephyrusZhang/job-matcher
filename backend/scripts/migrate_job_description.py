"""Collapse the jobs table's seven prose columns into ``description`` + ``requirements``.

    uv run python scripts/migrate_job_description.py            # convert in place
    uv run python scripts/migrate_job_description.py --truncate # start from empty
    uv run python scripts/migrate_job_description.py --dry-run

Dropped: ``responsibilities``, ``requirements_must``, ``requirements_nice``,
``department``, ``department_product``, ``education``, ``experience``,
``summary``. Six of those were NULL for every row in the shipped database; the
two that held data map straight across:

    description  ← responsibilities
    requirements ← requirements_must, rejoined with newlines

``requirements_must`` was only ever a JSON array because ``normalize_job`` split
the site's paragraph on newlines and semicolons on the way in. Rejoining is not
a perfect inverse — a source that used '；' as its separator comes back with
newlines — but it keeps the text rather than dropping it.

There is no migration framework here, so this rebuilds the table by hand:
SQLite cannot drop several columns and reorder the rest in one statement.
"""

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = BACKEND_DIR / "data" / "job_matcher.db"

NEW_SCHEMA = """
CREATE TABLE jobs_migrated (
    id           TEXT PRIMARY KEY,
    company_id   TEXT NOT NULL,
    title        TEXT NOT NULL,
    category     TEXT NOT NULL,
    location     TEXT,
    job_type     TEXT,
    description  TEXT,
    requirements TEXT,
    posted_date  TEXT,
    source_url   TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_jobs_company      ON jobs(company_id)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_category     ON jobs(category)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_location     ON jobs(location)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_job_type     ON jobs(job_type)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_posted_date  ON jobs(posted_date DESC)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_content_hash ON jobs(content_hash)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_source_url   ON jobs(source_url, company_id)",
]


def rejoin_requirements(raw: str | None) -> str:
    """Turn the stored ``requirements_must`` JSON array back into text."""
    if not raw:
        return ""
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        # Not JSON after all — it was already plain text.
        return raw
    if not isinstance(items, list):
        return str(items)
    return "\n".join(str(item) for item in items if item)


def column_names(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def migrate(db_path: Path, truncate: bool, dry_run: bool) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    columns = column_names(conn, "jobs")
    if not columns:
        print("No jobs table found — nothing to do.")
        return 0
    if "description" in columns and "responsibilities" not in columns:
        print("Already migrated.")
        return 0

    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    favorites = conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]

    if truncate:
        print(f"--truncate: dropping all {total} jobs and {favorites} favorites.")
    else:
        with_desc = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE responsibilities IS NOT NULL AND responsibilities <> ''"
        ).fetchone()[0]
        with_req = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE requirements_must NOT IN ('[]', '')"
        ).fetchone()[0]
        print(f"{total} jobs: {with_desc} carry a description, {with_req} carry requirements.")
        print(f"{favorites} favorites will be kept.")

    if dry_run:
        print("--dry-run: stopping before any write.")
        return 0

    backup = db_path.with_suffix(f".db.bak.{datetime.now():%Y%m%d_%H%M%S}")
    shutil.copy2(db_path, backup)
    print(f"Backed up to {backup.name}")

    # favorites has ON DELETE CASCADE against jobs(id). Dropping the old table
    # with foreign keys enforced would take the favorites with it, so keep them
    # off for the swap — they are off by default, this is belt and braces.
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(NEW_SCHEMA)

    moved = 0
    if not truncate:
        rows = conn.execute("SELECT * FROM jobs").fetchall()
        conn.executemany(
            """
            INSERT INTO jobs_migrated (id, company_id, title, category, location,
                                       job_type, description, requirements,
                                       posted_date, source_url, content_hash,
                                       created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["id"], row["company_id"], row["title"], row["category"],
                    row["location"], row["job_type"],
                    row["responsibilities"] or "",
                    rejoin_requirements(row["requirements_must"]),
                    row["posted_date"], row["source_url"], row["content_hash"],
                    row["created_at"], row["updated_at"],
                )
                for row in rows
            ],
        )
        moved = len(rows)

    conn.execute("DROP TABLE jobs")
    conn.execute("ALTER TABLE jobs_migrated RENAME TO jobs")
    for statement in INDEXES:
        conn.execute(statement)

    if truncate:
        conn.execute("DELETE FROM favorites")

    conn.commit()
    conn.execute("VACUUM")
    conn.close()

    print(f"Done: {moved} jobs carried over.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="drop every job and favorite instead of converting them",
    )
    parser.add_argument("--dry-run", action="store_true", help="report and exit")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"No database at {args.db}", file=sys.stderr)
        return 1
    return migrate(args.db, args.truncate, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
