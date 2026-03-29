"""Tests for database initialization and operations."""

import pytest
import pytest_asyncio


class TestDatabaseInit:
    async def test_tables_created(self, db):
        """All required tables should exist after init."""
        tables = await db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        table_names = {row["name"] for row in tables}
        expected = {"jobs", "favorites", "resume", "reports", "chat_messages", "crawl_tasks", "settings"}
        assert expected.issubset(table_names)

    async def test_settings_default_row(self, db):
        """Settings table should have a default row after init."""
        row = await db.fetch_one("SELECT * FROM settings WHERE id = 1")
        assert row is not None
        assert row["display_density"] == "comfortable"
        assert row["language"] == "zh"

    async def test_resume_single_row_constraint(self, db):
        """Resume table enforces single-row constraint (id=1)."""
        await db.execute(
            "INSERT INTO resume (id, filename, file_path, parsed_data) VALUES (1, 'a.pdf', '/tmp/a.pdf', '{}')"
        )
        with pytest.raises(Exception):
            await db.execute(
                "INSERT INTO resume (id, filename, file_path, parsed_data) VALUES (2, 'b.pdf', '/tmp/b.pdf', '{}')"
            )

    async def test_favorites_cascade_delete(self, db):
        """Deleting a job should cascade delete its favorites."""
        await db.execute(
            "INSERT INTO jobs (id, company_id, title, category, source_url, content_hash) "
            "VALUES ('j1', 'c1', 'Test Job', '后端', 'https://example.com', 'hash1')"
        )
        await db.execute("INSERT INTO favorites (job_id) VALUES ('j1')")
        await db.execute("DELETE FROM jobs WHERE id = 'j1'")
        row = await db.fetch_one("SELECT * FROM favorites WHERE job_id = 'j1'")
        assert row is None

    async def test_chat_messages_cascade_on_report_delete(self, db):
        """Deleting a report should cascade delete its chat messages."""
        await db.execute(
            "INSERT INTO reports (id, company_id, report_type, content, job_ids, preferences) "
            "VALUES ('r1', 'c1', 'match', 'report content', '[]', '{}')"
        )
        await db.execute(
            "INSERT INTO chat_messages (id, report_id, role, content) "
            "VALUES ('m1', 'r1', 'user', 'hello')"
        )
        await db.execute("DELETE FROM reports WHERE id = 'r1'")
        row = await db.fetch_one("SELECT * FROM chat_messages WHERE report_id = 'r1'")
        assert row is None

    async def test_reports_unique_constraint(self, db):
        """Each company can have at most one report per type."""
        await db.execute(
            "INSERT INTO reports (id, company_id, report_type, content, job_ids, preferences) "
            "VALUES ('r1', 'c1', 'match', 'content1', '[]', '{}')"
        )
        with pytest.raises(Exception):
            await db.execute(
                "INSERT INTO reports (id, company_id, report_type, content, job_ids, preferences) "
                "VALUES ('r2', 'c1', 'match', 'content2', '[]', '{}')"
            )


class TestDatabaseOperations:
    async def test_execute_and_fetch(self, db):
        """Basic execute and fetch operations."""
        await db.execute(
            "INSERT INTO jobs (id, company_id, title, category, source_url, content_hash) "
            "VALUES ('j1', 'c1', 'Frontend Dev', '前端', 'https://example.com', 'h1')"
        )
        row = await db.fetch_one("SELECT * FROM jobs WHERE id = 'j1'")
        assert row["title"] == "Frontend Dev"
        assert row["category"] == "前端"

    async def test_fetch_all(self, db):
        """Fetch multiple rows."""
        await db.execute(
            "INSERT INTO jobs (id, company_id, title, category, source_url, content_hash) "
            "VALUES ('j1', 'c1', 'Job 1', '后端', 'https://a.com', 'h1')"
        )
        await db.execute(
            "INSERT INTO jobs (id, company_id, title, category, source_url, content_hash) "
            "VALUES ('j2', 'c1', 'Job 2', '前端', 'https://b.com', 'h2')"
        )
        rows = await db.fetch_all("SELECT * FROM jobs WHERE company_id = 'c1'")
        assert len(rows) == 2

    async def test_execute_with_params(self, db):
        """Parameterized queries should work."""
        await db.execute(
            "INSERT INTO jobs (id, company_id, title, category, source_url, content_hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("j1", "c1", "Test", "算法", "https://x.com", "h1"),
        )
        row = await db.fetch_one("SELECT * FROM jobs WHERE id = ?", ("j1",))
        assert row["title"] == "Test"
