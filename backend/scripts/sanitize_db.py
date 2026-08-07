"""Strip personal data out of the tracked SQLite database.

    uv run python scripts/sanitize_db.py            # clean data/job_matcher.db
    uv run python scripts/sanitize_db.py --check     # report only, exit 1 if dirty
    uv run python scripts/sanitize_db.py --db other.db

``backend/data/job_matcher.db`` is committed on purpose — the crawled ``jobs``
are the point of a ``chore(db)`` commit. But the same file also accumulates the
things the app learns *about its user*: uploaded résumés parsed to raw text
(name, phone, email, school), every ``/match`` conversation, and favourites.
This repository is public, so those must never reach a commit.

Run this before committing the database. ``--check`` is the form to wire into a
pre-commit hook.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = BACKEND_DIR / "data" / "job_matcher.db"

#: Tables emptied before the database may be committed. `resume` is the
#: pre-migration singular table, still present in older commits.
PERSONAL_TABLES = (
    "resumes",
    "resume",
    "match_messages",
    "match_conversations",
    "favorites",
)

#: Kept: the crawled corpus and how it was obtained. None of it is about the user.
PUBLIC_TABLES = ("jobs", "companies", "crawler_scripts", "crawl_tasks", "settings")


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Rows currently held in each personal table."""
    found = {}
    for table in PERSONAL_TABLES:
        if table_exists(conn, table):
            found[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return found


def sanitize(db_path: Path, check_only: bool) -> int:
    conn = sqlite3.connect(db_path)
    before = counts(conn)
    dirty = {t: n for t, n in before.items() if n}

    if check_only:
        conn.close()
        if dirty:
            print(f"{db_path.name} still holds personal data:", file=sys.stderr)
            for table, n in dirty.items():
                print(f"  {table}: {n} rows", file=sys.stderr)
            print("Run: uv run python scripts/sanitize_db.py", file=sys.stderr)
            return 1
        print(f"{db_path.name}: clean")
        return 0

    if not dirty:
        print(f"{db_path.name}: already clean")
        conn.close()
        return 0

    for table in dirty:
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    # VACUUM rewrites the file; without it the deleted rows stay readable in
    # free pages, and a committed .db is a blob anyone can carve.
    conn.execute("VACUUM")

    kept = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in PUBLIC_TABLES
        if table_exists(conn, t)
    }
    conn.close()

    print(f"{db_path.name}: cleared " + ", ".join(f"{t}={n}" for t, n in dirty.items()))
    print("  kept " + ", ".join(f"{t}={n}" for t, n in kept.items()))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report and exit non-zero if personal data is present; change nothing",
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"No database at {args.db}", file=sys.stderr)
        return 1
    return sanitize(args.db, args.check)


if __name__ == "__main__":
    raise SystemExit(main())
