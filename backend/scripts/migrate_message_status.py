"""Add ``status`` and ``seq`` to ``match_messages``.

A turn used to be written once, at the very end. It is now inserted as
``running`` and updated frame by frame so a client that reconnects mid-turn can
resume, which needs two new columns:

``status``
    ``running`` | ``completed`` | ``stopped`` | ``failed`` | ``interrupted``.
``seq``
    Frames folded into the row so far — the resume anchor.

Existing rows were all written on completion, so the ``completed`` default is
already correct and no backfill is needed.

Usage:
    uv run python scripts/migrate_message_status.py [--db path]
"""

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "job_matcher.db"

_COLUMNS = {
    "status": "TEXT NOT NULL DEFAULT 'completed'",
    "seq": "INTEGER NOT NULL DEFAULT 0",
}


def migrate(db_path: Path) -> None:
    """Add the columns if they are missing."""
    if not db_path.exists():
        raise SystemExit(f"database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "match_messages" not in tables:
            print("no match_messages table — nothing to do")
            return

        existing = {r[1] for r in conn.execute("PRAGMA table_info(match_messages)")}
        missing = {name: ddl for name, ddl in _COLUMNS.items() if name not in existing}
        if not missing:
            print("already migrated")
            return

        backup = db_path.with_suffix(f".bak.{datetime.now():%Y%m%d%H%M%S}")
        shutil.copy2(db_path, backup)
        print(f"backup written to {backup}")

        for name, ddl in missing.items():
            conn.execute(f"ALTER TABLE match_messages ADD COLUMN {name} {ddl}")
            print(f"added column {name}")

        # Any row left as `running` predates this migration's write path and can
        # never be resumed — its agent task died with the old process.
        stale = conn.execute(
            "UPDATE match_messages SET status = 'interrupted' WHERE status = 'running'"
        ).rowcount
        if stale:
            print(f"marked {stale} stale running row(s) as interrupted")

        conn.commit()
        print("done")
    finally:
        conn.close()


def main() -> None:
    """Parse arguments and run the migration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    migrate(parser.parse_args().db)


if __name__ == "__main__":
    main()
