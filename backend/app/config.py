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
    api_key: str = ""
    base_url: str | None = None
    model: str = "gpt-4o-mini"
    model_report: str = "gpt-4o"
    max_tokens_report: int = 4096
    max_tokens_chat: int = 2048
    temperature: float = 0.7


class CrawlConfig(BaseModel):
    browser_headless: bool = True
    page_load_timeout: int = 30000
    max_scroll_attempts: int = 20
    concurrent_companies: int = 2


class CompanyConfig(BaseModel):
    id: str
    name: str
    career_url: str
    crawl_interval_hours: int = 12


class AppConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    uploads: UploadConfig = UploadConfig()
    llm: LLMConfig = LLMConfig()
    crawl: CrawlConfig = CrawlConfig()
    companies: list[CompanyConfig] = []


_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def _resolve_env_vars(value: str) -> str:
    """Replace ${ENV_VAR} placeholders with environment variable values."""
    def replacer(match: re.Match) -> str:
        env_name = match.group(1)
        return os.environ.get(env_name, "")
    return _ENV_VAR_PATTERN.sub(replacer, value)


def _resolve_env_recursive(obj):
    """Recursively resolve env vars in a nested dict/list structure."""
    if isinstance(obj, str):
        return _resolve_env_vars(obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_recursive(item) for item in obj]
    return obj


def load_config(config_dir: str | None = None) -> AppConfig:
    """Load and merge settings.yml + companies.yml into AppConfig."""
    if config_dir is None:
        config_dir = str(Path(__file__).resolve().parent.parent / "config")

    # Load .env from backend/ root (next to config/)
    env_path = Path(config_dir).parent / ".env"
    load_dotenv(env_path, override=False)

    settings_path = Path(config_dir) / "settings.yml"
    companies_path = Path(config_dir) / "companies.yml"

    settings_data = {}
    if settings_path.exists():
        with open(settings_path) as f:
            settings_data = yaml.safe_load(f) or {}

    companies_data = {}
    if companies_path.exists():
        with open(companies_path) as f:
            companies_data = yaml.safe_load(f) or {}

    settings_data = _resolve_env_recursive(settings_data)
    companies_data = _resolve_env_recursive(companies_data)

    merged = {**settings_data, "companies": companies_data.get("companies", [])}
    return AppConfig(**merged)
