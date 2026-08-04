"""Migrate the singleton ``resume`` table to the multi-row ``resumes`` table.

The old schema allowed exactly one resume (``CHECK (id = 1)``). This copies that
row into ``resumes``, marks it as the default, and leaves the old table in place
so the migration can be re-run or inspected.

Usage:
    uv run python scripts/migrate_multi_resume.py [--db path] [--drop-old]
"""

import argparse
import json
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "job_matcher.db"

CREATE_RESUMES = """
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
"""


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    """Return whether a table is present."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def migrate(db_path: Path, drop_old: bool) -> None:
    """Copy the singleton resume row into the new table."""
    if not db_path.exists():
        raise SystemExit(f"database not found: {db_path}")

    backup = db_path.with_suffix(f".db.bak-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    shutil.copy2(db_path, backup)
    print(f"backup written to {backup}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(CREATE_RESUMES)

        if not table_exists(conn, "resume"):
            print("no legacy `resume` table — nothing to copy")
        else:
            existing = conn.execute("SELECT COUNT(*) FROM resumes").fetchone()[0]
            if existing:
                print(f"`resumes` already has {existing} row(s) — skipping copy")
            else:
                row = conn.execute("SELECT * FROM resume WHERE id = 1").fetchone()
                if row is None:
                    print("legacy table is empty — nothing to copy")
                else:
                    # Keep the payload verbatim; it is already JSON text.
                    parsed = row["parsed_data"]
                    json.loads(parsed)  # fail loudly on corrupt data
                    conn.execute(
                        """
                        INSERT INTO resumes
                            (id, filename, file_path, parsed_data, label, is_default, uploaded_at)
                        VALUES (?, ?, ?, ?, ?, 1, ?)
                        """,
                        (
                            str(uuid.uuid4()),
                            row["filename"],
                            row["file_path"],
                            parsed,
                            row["filename"],
                            row["uploaded_at"],
                        ),
                    )
                    print(f"copied 1 resume ({row['filename']}) and marked it default")

            if drop_old:
                conn.execute("DROP TABLE resume")
                print("dropped legacy `resume` table")

        conn.commit()

        total = conn.execute("SELECT COUNT(*) FROM resumes").fetchone()[0]
        defaults = conn.execute("SELECT COUNT(*) FROM resumes WHERE is_default = 1").fetchone()[0]
        print(f"done: {total} resume(s), {defaults} marked default")
        if total and defaults != 1:
            print("WARNING: expected exactly one default resume")
    finally:
        conn.close()


def main() -> None:
    """Parse arguments and run the migration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="path to job_matcher.db")
    parser.add_argument(
        "--drop-old", action="store_true", help="drop the legacy `resume` table after copying"
    )
    args = parser.parse_args()
    migrate(args.db, args.drop_old)


if __name__ == "__main__":
    main()
