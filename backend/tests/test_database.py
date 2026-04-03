import pytest
import aiosqlite

from app.config import DatabaseConfig
from app.database import init_database


@pytest.mark.asyncio
async def test_init_database(tmp_path):
    """Test database initialization creates all tables."""
    db_path = str(tmp_path / "test.db")
    config = DatabaseConfig(path=db_path)
    await init_database(config)

    async with aiosqlite.connect(db_path) as db:
        # Check tables exist
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ) as cursor:
            tables = [row[0] for row in await cursor.fetchall()]

        expected = ["chat_messages", "crawl_tasks", "favorites", "jobs", "reports", "resume", "settings"]
        for t in expected:
            assert t in tables, f"Table {t} not found"

        # Check settings has default row
        async with db.execute("SELECT * FROM settings WHERE id = 1") as cursor:
            row = await cursor.fetchone()
            assert row is not None


@pytest.mark.asyncio
async def test_init_database_idempotent(tmp_path):
    """Test that calling init_database twice doesn't fail."""
    db_path = str(tmp_path / "test.db")
    config = DatabaseConfig(path=db_path)
    await init_database(config)
    await init_database(config)  # Should not raise
