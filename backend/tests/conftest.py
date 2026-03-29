"""Shared pytest fixtures for all tests."""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient



@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Create temporary config files for testing."""
    settings = tmp_path / "settings.yml"
    settings.write_text(
        """
server:
  host: "127.0.0.1"
  port: 8000
  cors_origins: ["http://localhost:3000"]

database:
  path: ":memory:"

uploads:
  dir: "{upload_dir}"
  max_size_mb: 10
  allowed_types:
    - "application/pdf"
    - "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

llm:
  base_url: "http://localhost:11434/v1"
  api_key: "not-needed"
  model: "test-model"
  model_report: "test-model"
  max_tokens_report: 4096
  max_tokens_chat: 2048
  temperature: 0.7

crawl:
  browser_headless: true
  page_load_timeout: 30000
  max_scroll_attempts: 20
  concurrent_companies: 2
""".format(upload_dir=str(tmp_path / "uploads"))
    )

    companies = tmp_path / "companies.yml"
    companies.write_text(
        """
companies:
  - id: test_company
    name: 测试公司
    career_url: "https://example.com/jobs"
    crawl_interval_hours: 24

  - id: test_company_2
    name: 测试公司二
    career_url: "https://example.com/jobs2"
    crawl_interval_hours: 12
"""
    )

    return tmp_path


@pytest.fixture
def app_config(config_dir: Path):
    """Load AppConfig from temporary config files."""
    from app.config import load_config

    return load_config(
        settings_path=config_dir / "settings.yml",
        companies_path=config_dir / "companies.yml",
    )


@pytest_asyncio.fixture
async def db(app_config):
    """In-memory SQLite database for testing."""
    from app.database import Database

    database = Database(app_config.database)
    await database.init()
    yield database
    await database.close()


@pytest_asyncio.fixture
async def client(app_config, db):
    """Async HTTP test client."""
    from app.main import create_app

    app = create_app(config=app_config, database=db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
