import json
import uuid
import pytest

from app.models import job as job_model
from app.models import favorite as fav_model
from app.models import resume as resume_model
from app.models import report as report_model
from app.models import chat as chat_model
from app.models import crawl_task as task_model


@pytest.mark.asyncio
async def test_job_crud(seeded_db):
    """Test job query operations."""
    db = seeded_db
    jobs = db._test_jobs

    # Test get_jobs with company filter
    result, total = await job_model.get_jobs(db, "bytedance")
    assert total == 2
    assert len(result) == 2

    # Test get_jobs with category filter
    result, total = await job_model.get_jobs(db, "bytedance", category="前端")
    assert total == 1
    assert result[0]["category"] == "前端"

    # Test get_job_by_id
    job = await job_model.get_job_by_id(db, jobs[0]["id"])
    assert job is not None
    assert job["title"] == "前端开发工程师"

    # Test non-existent job
    job = await job_model.get_job_by_id(db, "nonexistent")
    assert job is None


@pytest.mark.asyncio
async def test_job_search(seeded_db):
    """Test job search functionality."""
    db = seeded_db

    results, total = await job_model.search_jobs(db, "前端")
    assert total >= 1
    assert any("前端" in r["title"] for r in results)


@pytest.mark.asyncio
async def test_job_suggest(seeded_db):
    """Test job suggestions."""
    db = seeded_db
    suggestions = await job_model.suggest_jobs(db, "前端")
    assert len(suggestions) >= 1


@pytest.mark.asyncio
async def test_favorite_crud(seeded_db):
    """Test favorite add/remove/list."""
    db = seeded_db
    job_id = db._test_jobs[0]["id"]

    # Add favorite
    created_at = await fav_model.add_favorite(db, job_id)
    assert created_at is not None

    # Check is_favorited
    assert await fav_model.is_favorited(db, job_id) is True
    assert await fav_model.is_favorited(db, "nonexistent") is False

    # List favorites
    favs = await fav_model.get_favorites(db)
    assert len(favs) == 1
    assert favs[0]["job_id"] == job_id

    # List by company
    favs = await fav_model.get_favorites(db, company_id="bytedance")
    assert len(favs) == 1

    favs = await fav_model.get_favorites(db, company_id="tencent")
    assert len(favs) == 0

    # Summary
    summary = await fav_model.get_favorites_summary(db)
    assert len(summary) == 1
    assert summary[0]["count"] == 1

    # Remove
    await fav_model.remove_favorite(db, job_id)
    assert await fav_model.is_favorited(db, job_id) is False


@pytest.mark.asyncio
async def test_resume_crud(seeded_db):
    """Test resume upsert/get/delete."""
    db = seeded_db

    # Initially empty
    assert await resume_model.get_resume(db) is None

    # Upsert
    parsed = {"skills": ["Python"], "experience_years": 2, "education": "本科"}
    await resume_model.upsert_resume(db, "test.pdf", "/path/test.pdf", parsed)

    resume = await resume_model.get_resume(db)
    assert resume is not None
    assert resume["filename"] == "test.pdf"
    assert resume["parsed_data"]["skills"] == ["Python"]

    # Replace
    parsed2 = {"skills": ["Go", "Python"], "experience_years": 3, "education": "硕士"}
    await resume_model.upsert_resume(db, "new.pdf", "/path/new.pdf", parsed2)

    resume = await resume_model.get_resume(db)
    assert resume["filename"] == "new.pdf"

    # Delete
    await resume_model.delete_resume(db)
    assert await resume_model.get_resume(db) is None


@pytest.mark.asyncio
async def test_report_crud(seeded_db):
    """Test report upsert/get/delete."""
    db = seeded_db
    report_id = str(uuid.uuid4())

    await report_model.upsert_report(
        db, report_id, "bytedance", "match",
        "# Report", ["j1", "j2"],
        {"interest": "前端", "additional": ""},
    )

    report = await report_model.get_report(db, "bytedance", "match")
    assert report is not None
    assert report["content"] == "# Report"
    assert report["job_ids"] == ["j1", "j2"]

    # Get by ID
    report = await report_model.get_report_by_id(db, report_id)
    assert report is not None

    # Delete
    deleted = await report_model.delete_report(db, "bytedance", "match")
    assert deleted == 1

    report = await report_model.get_report(db, "bytedance", "match")
    assert report is None


@pytest.mark.asyncio
async def test_chat_crud(seeded_db):
    """Test chat message insert and history."""
    db = seeded_db

    # Create a report first
    report_id = str(uuid.uuid4())
    await report_model.upsert_report(
        db, report_id, "bytedance", "match",
        "Report", ["j1"], {"interest": "test", "additional": ""},
    )

    # Insert messages
    msg1_id = str(uuid.uuid4())
    msg2_id = str(uuid.uuid4())
    await chat_model.insert_message(db, msg1_id, report_id, "user", "Hello")
    await chat_model.insert_message(db, msg2_id, report_id, "assistant", "Hi there")

    history = await chat_model.get_chat_history(db, report_id)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"

    # Cascade delete: delete report should delete messages
    await report_model.delete_report(db, "bytedance", "match")
    history = await chat_model.get_chat_history(db, report_id)
    assert len(history) == 0


@pytest.mark.asyncio
async def test_crawl_task_crud(seeded_db):
    """Test crawl task operations."""
    db = seeded_db
    task_id = str(uuid.uuid4())

    # Create
    await task_model.create_task(db, task_id, "bytedance")

    # Has active
    assert await task_model.has_active_task(db, "bytedance") is True
    assert await task_model.has_active_task(db, "tencent") is False

    # Get by ID
    task = await task_model.get_task_by_id(db, task_id)
    assert task is not None
    assert task["status"] == "pending"

    # Update to running
    await task_model.update_task_status(db, task_id, "running")
    task = await task_model.get_task_by_id(db, task_id)
    assert task["status"] == "running"
    assert task["started_at"] is not None

    # Update to completed
    await task_model.update_task_status(
        db, task_id, "completed", jobs_found=10, jobs_new=5, jobs_updated=2
    )
    task = await task_model.get_task_by_id(db, task_id)
    assert task["status"] == "completed"
    assert task["jobs_found"] == 10

    # No longer active
    assert await task_model.has_active_task(db, "bytedance") is False

    # List tasks
    tasks, total = await task_model.get_tasks(db)
    assert total >= 1
