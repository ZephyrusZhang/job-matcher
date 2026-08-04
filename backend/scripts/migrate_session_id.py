"""Rename ``match_messages.conversation_id`` to ``session_id``.

The column was renamed to match the agent framework's vocabulary, where a
conversation id is also the LangGraph thread/session id.

Usage:
    uv run python scripts/migrate_session_id.py [--db path]
"""

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "job_matcher.db"


def migrate(db_path: Path) -> None:
    """Rename the column when the old name is still present."""
    if not db_path.exists():
        raise SystemExit(f"database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "match_messages" not in tables:
            print("no match_messages table — nothing to do")
            return

        columns = {r[1] for r in conn.execute("PRAGMA table_info(match_messages)")}
        if "session_id" in columns:
            print("already migrated")
            return
        if "conversation_id" not in columns:
            print("unexpected schema — neither column present")
            return

        backup = db_path.with_suffix(f".db.bak-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        shutil.copy2(db_path, backup)
        print(f"backup written to {backup}")

        conn.execute("ALTER TABLE match_messages RENAME COLUMN conversation_id TO session_id")
        conn.execute("DROP INDEX IF EXISTS idx_match_msg_conv")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_match_msg_session "
            "ON match_messages(session_id, created_at)"
        )
        conn.commit()
        print("renamed conversation_id -> session_id")
    finally:
        conn.close()


def main() -> None:
    """Parse arguments and run the migration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    migrate(parser.parse_args().db)


if __name__ == "__main__":
    main()
