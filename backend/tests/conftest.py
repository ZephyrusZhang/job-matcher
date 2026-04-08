import asyncio
import json
import os
import uuid
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Set dummy env vars before importing app
os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.config import AppConfig, load_config
from app.database import init_database, get_db
from app.dependencies import init_services
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Create a temporary test database."""
    db_path = str(tmp_path / "test.db")
    from app.config import DatabaseConfig
    await init_database(DatabaseConfig(path=db_path))
    db = await get_db(db_path)
    yield db
    await db.close()


@pytest_asyncio.fixture
async def seeded_db(test_db):
    """Database with sample job data."""
    jobs = [
        {
            "id": str(uuid.uuid4()),
            "company_id": "bytedance",
            "title": "前端开发工程师",
            "category": "前端",
            "location": "北京",
            "job_type": "全职",
            "responsibilities": "负责前端开发",
            "requirements_must": json.dumps(["React", "TypeScript"]),
            "requirements_nice": json.dumps(["GraphQL"]),
            "department": "抖音",
            "department_product": "抖音App",
            "education": "本科",
            "experience": "2年",
            "posted_date": "2026-03-27",
            "source_url": "https://example.com/1",
            "summary": "前端开发",
            "content_hash": "hash1",
        },
        {
            "id": str(uuid.uuid4()),
            "company_id": "bytedance",
            "title": "后端开发工程师",
            "category": "后端",
            "location": "上海",
            "job_type": "实习",
            "responsibilities": "负责后端开发",
            "requirements_must": json.dumps(["Go", "MySQL"]),
            "requirements_nice": json.dumps(["Redis"]),
            "department": "飞书",
            "department_product": "飞书",
            "education": "本科",
            "experience": "无",
            "posted_date": "2026-03-28",
            "source_url": "https://example.com/2",
            "summary": "后端开发",
            "content_hash": "hash2",
        },
        {
            "id": str(uuid.uuid4()),
            "company_id": "tencent",
            "title": "算法工程师",
            "category": "算法",
            "location": "深圳",
            "job_type": "全职",
            "responsibilities": "负责推荐算法",
            "requirements_must": json.dumps(["Python", "PyTorch"]),
            "requirements_nice": json.dumps(["TensorFlow"]),
            "department": "微信",
            "department_product": "微信",
            "education": "硕士",
            "experience": "3年",
            "posted_date": "2026-03-29",
            "source_url": "https://example.com/3",
            "summary": "推荐算法",
            "content_hash": "hash3",
        },
    ]

    for job in jobs:
        await test_db.execute(
            """INSERT INTO jobs (id, company_id, title, category, location, job_type,
                               responsibilities, requirements_must, requirements_nice,
                               department, department_product, education, experience,
                               posted_date, source_url, summary, content_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            tuple(job.values()),
        )
    await test_db.commit()

    # Store job IDs for reference
    test_db._test_jobs = jobs
    yield test_db


@pytest_asyncio.fixture
async def client(tmp_path):
    """HTTP test client with initialized app."""
    backend_dir = Path(__file__).resolve().parent.parent
    config = load_config(str(backend_dir / "config"))
    config.database.path = str(tmp_path / "api_test.db")
    config.uploads.dir = str(tmp_path / "uploads")

    await init_database(config.database)
    init_services(config)

    # Seed some data
    db = await get_db(config.database.path)
    jobs = [
        ("j1", "bytedance", "前端工程师", "前端", "北京", "全职",
         "前端开发", '["React"]', '["Vue"]', "抖音", "抖音", "本科", "2年",
         "2026-03-27", "https://example.com/1", "前端", "h1"),
        ("j2", "bytedance", "后端工程师", "后端", "上海", "实习",
         "后端开发", '["Go"]', '[]', "飞书", "飞书", "本科", "无",
         "2026-03-28", "https://example.com/2", "后端", "h2"),
        ("j3", "tencent", "算法工程师", "算法", "深圳", "全职",
         "算法开发", '["Python"]', '[]', "微信", "微信", "硕士", "3年",
         "2026-03-29", "https://example.com/3", "算法", "h3"),
    ]
    for j in jobs:
        await db.execute(
            """INSERT INTO jobs (id, company_id, title, category, location, job_type,
                               responsibilities, requirements_must, requirements_nice,
                               department, department_product, education, experience,
                               posted_date, source_url, summary, content_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            j,
        )
    await db.commit()
    await db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
