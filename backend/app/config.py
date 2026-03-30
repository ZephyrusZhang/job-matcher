"""Configuration loading from YAML files with environment variable substitution."""

import os
import re
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]


class DatabaseConfig(BaseModel):
    path: str = "data/job_matcher.db"


class UploadConfig(BaseModel):
    dir: str = "data/uploads"
    max_size_mb: int = 10
    allowed_types: list[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]


class LLMConfig(BaseModel):
    base_url: str = "http://localhost:11434/v1"
    api_key: str = "not-needed"
    model: str = "qwen2.5"
    model_report: str = "qwen2.5"
    max_tokens_report: int = 4096
    max_tokens_chat: int = 2048
    temperature: float = 0.7


class CrawlConfig(BaseModel):
    browser_headless: bool = True
    page_load_timeout: int = 30000
    max_scroll_attempts: int = 20
    concurrent_companies: int = 2
    agent_learning_pages: int = 1   # Agent 分析的最大页数
    agent_lock_threshold: int = 1   # 连续一致次数阈值后锁定


class CompanyConfig(BaseModel):
    id: str
    name: str
    career_url: str
    crawl_interval_hours: int = 12
    max_pages: int = -1  # 爬取页数，-1 表示全部爬取
    # 可选 hint：手动指定岗位卡片 CSS 选择器，跳过 Agent 分析。留空则由 Agent 自动发现。
    job_card_selector: str = ""


class AppConfig(BaseModel):
    server: ServerConfig
    database: DatabaseConfig
    uploads: UploadConfig
    llm: LLMConfig
    crawl: CrawlConfig
    companies: list[CompanyConfig]


_ENV_PATTERN = re.compile(r"\$\{(\w+)(?::-(.*?))?\}")


def _resolve_env_vars(obj):
    """Recursively resolve ${ENV_VAR} and ${ENV_VAR:-default} placeholders."""
    if isinstance(obj, str):
        return _ENV_PATTERN.sub(
            lambda m: os.environ.get(m.group(1)) or m.group(2) or m.group(0), obj
        )
    if isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_vars(item) for item in obj]
    return obj


def load_config(
    settings_path: Path | None = None,
    companies_path: Path | None = None,
) -> AppConfig:
    """Load and validate configuration from YAML files."""
    base_dir = Path(__file__).parent.parent
    load_dotenv(base_dir / ".env")
    if settings_path is None:
        settings_path = base_dir / "config" / "settings.yml"
    if companies_path is None:
        companies_path = base_dir / "config" / "companies.yml"

    with open(settings_path) as f:
        settings_data = yaml.safe_load(f)

    with open(companies_path) as f:
        companies_data = yaml.safe_load(f)

    settings_data = _resolve_env_vars(settings_data)
    companies_data = _resolve_env_vars(companies_data)

    merged = {**settings_data, "companies": companies_data.get("companies", [])}
    return AppConfig(**merged)
