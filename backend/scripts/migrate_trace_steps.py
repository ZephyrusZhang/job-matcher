"""Convert ``match_messages.tool_events`` into the ordered ``steps`` trace.

The trace used to be a bare list of tool calls with narration stored separately.
It is now one ordered array mixing ``narration`` and ``tool`` entries, so old
rows get their tool entries stamped with a type and position, and the message's
narration (``content``) is prepended as the first step.

Usage:
    uv run python scripts/migrate_trace_steps.py [--db path]
"""

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "job_matcher.db"


def migrate(db_path: Path) -> None:
    """Rename the column and reshape its payload."""
    if not db_path.exists():
        raise SystemExit(f"database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "match_messages" not in tables:
            print("no match_messages table — nothing to do")
            return

        columns = {r[1] for r in conn.execute("PRAGMA table_info(match_messages)")}
        if "steps" in columns:
            print("already migrated")
            return
        if "tool_events" not in columns:
            print("unexpected schema — neither column present")
            return

        backup = db_path.with_suffix(f".db.bak-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        shutil.copy2(db_path, backup)
        print(f"backup written to {backup}")

        conn.execute("ALTER TABLE match_messages RENAME COLUMN tool_events TO steps")

        converted = 0
        rows = conn.execute("SELECT id, content, steps FROM match_messages").fetchall()
        for row in rows:
            try:
                tools = json.loads(row["steps"]) if row["steps"] else []
            except json.JSONDecodeError:
                tools = []
            if not isinstance(tools, list):
                tools = []

            steps: list[dict] = []
            if row["content"]:
                steps.append({"type": "narration", "index": 0, "content": row["content"]})
            for tool in tools:
                if isinstance(tool, dict):
                    steps.append({**tool, "type": "tool", "index": len(steps)})

            conn.execute(
                "UPDATE match_messages SET steps = ? WHERE id = ?",
                (json.dumps(steps, ensure_ascii=False) if steps else None, row["id"]),
            )
            converted += 1

        conn.commit()
        print(f"renamed tool_events -> steps and reshaped {converted} row(s)")
    finally:
        conn.close()


def main() -> None:
    """Parse arguments and run the migration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    migrate(parser.parse_args().db)


if __name__ == "__main__":
    main()
