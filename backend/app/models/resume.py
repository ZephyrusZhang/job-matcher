"""Data access for resumes.

Resumes used to be a singleton row (``resume`` table, ``CHECK (id = 1)``). They
are now a normal collection so several can be kept and matched against
selectively. Exactly one row carries ``is_default``, which is what callers that
don't name a resume get back.
"""

import json
import uuid

import aiosqlite


def _row_to_dict(row: aiosqlite.Row) -> dict:
    """Decode a resume row, parsing its JSON payload."""
    data = dict(row)
    data["parsed_data"] = json.loads(data["parsed_data"])
    data["is_default"] = bool(data["is_default"])
    return data


async def create_resume(
    db: aiosqlite.Connection,
    filename: str,
    file_path: str,
    parsed_data: dict,
    label: str = "",
    make_default: bool = False,
) -> dict:
    """Insert a resume, optionally promoting it to the default.

    Args:
        db: Open connection.
        filename: Original upload name.
        file_path: Where the file was stored.
        parsed_data: Structured resume produced by the LLM.
        label: Human-friendly name; falls back to the filename.
        make_default: Promote this resume to the default. The first resume
            always becomes the default regardless.

    Returns:
        The stored resume.
    """
    resume_id = str(uuid.uuid4())

    async with db.execute("SELECT COUNT(*) FROM resumes") as cursor:
        is_first = (await cursor.fetchone())[0] == 0

    should_default = make_default or is_first
    if should_default:
        await db.execute("UPDATE resumes SET is_default = 0")

    await db.execute(
        """
        INSERT INTO resumes (id, filename, file_path, parsed_data, label, is_default)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            resume_id,
            filename,
            file_path,
            json.dumps(parsed_data, ensure_ascii=False),
            label or filename,
            1 if should_default else 0,
        ),
    )
    await db.commit()
    return await get_resume(db, resume_id)  # type: ignore[return-value]


async def get_resume(db: aiosqlite.Connection, resume_id: str | None = None) -> dict | None:
    """Return one resume.

    Args:
        db: Open connection.
        resume_id: Which resume to fetch. ``None`` returns the default, falling
            back to the newest upload when no default is set.

    Returns:
        The resume, or ``None`` when none are stored.
    """
    if resume_id:
        query = "SELECT * FROM resumes WHERE id = ?"
        params: tuple = (resume_id,)
    else:
        query = "SELECT * FROM resumes ORDER BY is_default DESC, uploaded_at DESC LIMIT 1"
        params = ()

    async with db.execute(query, params) as cursor:
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None


async def list_resumes(db: aiosqlite.Connection) -> list[dict]:
    """Return every resume, default first then newest."""
    async with db.execute(
        "SELECT * FROM resumes ORDER BY is_default DESC, uploaded_at DESC"
    ) as cursor:
        return [_row_to_dict(row) for row in await cursor.fetchall()]


async def set_default_resume(db: aiosqlite.Connection, resume_id: str) -> bool:
    """Make one resume the default. Returns ``False`` when it does not exist."""
    async with db.execute("SELECT 1 FROM resumes WHERE id = ?", (resume_id,)) as cursor:
        if not await cursor.fetchone():
            return False

    await db.execute("UPDATE resumes SET is_default = 0")
    await db.execute("UPDATE resumes SET is_default = 1 WHERE id = ?", (resume_id,))
    await db.commit()
    return True


async def rename_resume(db: aiosqlite.Connection, resume_id: str, label: str) -> bool:
    """Change a resume's label. Returns ``False`` when it does not exist."""
    cursor = await db.execute("UPDATE resumes SET label = ? WHERE id = ?", (label, resume_id))
    await db.commit()
    return cursor.rowcount > 0


async def delete_resume(db: aiosqlite.Connection, resume_id: str) -> bool:
    """Delete a resume, promoting another to default when needed.

    Args:
        db: Open connection.
        resume_id: Resume to delete.

    Returns:
        ``False`` when the resume does not exist.
    """
    async with db.execute("SELECT is_default FROM resumes WHERE id = ?", (resume_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return False
        was_default = bool(row["is_default"])

    await db.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))

    if was_default:
        # Keep exactly one default alive so unqualified lookups stay stable.
        async with db.execute("SELECT id FROM resumes ORDER BY uploaded_at DESC LIMIT 1") as cursor:
            next_row = await cursor.fetchone()
        if next_row:
            await db.execute("UPDATE resumes SET is_default = 1 WHERE id = ?", (next_row["id"],))

    await db.commit()
    return True


async def count_resumes(db: aiosqlite.Connection) -> int:
    """Return how many resumes are stored."""
    async with db.execute("SELECT COUNT(*) FROM resumes") as cursor:
        return (await cursor.fetchone())[0]
