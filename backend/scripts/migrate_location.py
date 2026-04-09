"""One-shot migration: convert the jobs.location column from raw strings
to JSON arrays of city names.

Run from backend/ with:  uv run python scripts/migrate_location.py
"""
import json
import sqlite3
import sys
from pathlib import Path

# Make `app.*` importable when running the script directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.crawl.location import normalize_location  # noqa: E402

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "job_matcher.db"


def main() -> None:
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute("SELECT id, location FROM jobs").fetchall()
    total = len(rows)
    migrated = 0
    already_json = 0
    skipped = 0

    for row in rows:
        raw = row["location"]
        if raw is None:
            new_value = "[]"
        elif isinstance(raw, str) and raw.lstrip().startswith("["):
            # Already migrated
            already_json += 1
            continue
        else:
            cities = normalize_location(raw)
            new_value = json.dumps(cities, ensure_ascii=False)

        if new_value == raw:
            skipped += 1
            continue

        cur.execute("UPDATE jobs SET location = ? WHERE id = ?", (new_value, row["id"]))
        migrated += 1

    conn.commit()
    conn.close()

    print(f"Total rows: {total}")
    print(f"  Migrated:    {migrated}")
    print(f"  Already JSON: {already_json}")
    print(f"  Unchanged:   {skipped}")


if __name__ == "__main__":
    main()
