"""Agent framework configuration management.

Ported from the fastapi-langgraph-agent template. Handles environment detection,
``.env`` loading and typed access to every framework setting.

This is deliberately separate from ``app.config``, which loads the *business*
configuration (SQLite path, uploads, crawl tuning) from ``config/settings.yml``.
Nothing here touches the existing business config.
"""

import os
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv


class Environment(str, Enum):
    """Application environment types."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


def get_environment() -> Environment:
    """Get the current environment from ``APP_ENV``.

    Returns:
        Environment: The current environment.
    """
    match os.getenv("APP_ENV", "development").lower():
        case "production" | "prod":
            return Environment.PRODUCTION
        case "staging" | "stage":
            return Environment.STAGING
        case "test":
            return Environment.TEST
        case _:
            return Environment.DEVELOPMENT


def load_env_file() -> str | None:
    """Load the environment-specific .env file from the backend root.

    Returns:
        The path of the loaded file, or ``None`` when no candidate exists.
    """
    env = get_environment()
    base_dir = Path(__file__).resolve().parent.parent.parent

    env_files = [
        base_dir / f".env.{env.value}.local",
        base_dir / f".env.{env.value}",
        base_dir / ".env.local",
        base_dir / ".env",
    ]

    for env_file in env_files:
        if env_file.is_file():
            load_dotenv(dotenv_path=env_file, override=False)
            return str(env_file)

    return None


ENV_FILE = load_env_file()


def _bool_env(key: str, default: bool = False) -> bool:
    """Read a boolean environment variable."""
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("true", "1", "t", "yes", "on")


def parse_list_from_env(env_key: str, default: list[str] | None = None) -> list[str]:
    """Parse a comma-separated list from an environment variable."""
    value = os.getenv(env_key)
    if not value:
        return default or []

    value = value.strip("\"'")
    if "," not in value:
        return [value]
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    """Agent framework settings, loaded from environment variables."""

    def __init__(self):
        """Load all configuration values, then apply environment overrides."""
        self.ENVIRONMENT = get_environment()

        # Application
        self.PROJECT_NAME = os.getenv("PROJECT_NAME", "JobMatcher")
        self.VERSION = os.getenv("VERSION", "0.1.0")
        self.API_V1_STR = os.getenv("API_V1_STR", "/api/v1")
        self.DEBUG = _bool_env("DEBUG", False)

        # Langfuse observability
        self.LANGFUSE_TRACING_ENABLED = _bool_env("LANGFUSE_TRACING_ENABLED", False)
        self.LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        self.LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
        self.LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

        # LLM. Reuses the LLM_* variables the crawler agent already relies on,
        # so the framework and the existing crawler share one set of credentials.
        self.LLM_API_KEY = os.getenv("LLM_API_KEY", "")
        self.LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL") or os.getenv("LLM_MODEL", "deepseek-chat")
        # Comma-separated fallback chain; the default model is always first.
        self.LLM_FALLBACK_MODELS = parse_list_from_env("LLM_FALLBACK_MODELS", [])
        self.DEFAULT_LLM_TEMPERATURE = float(os.getenv("DEFAULT_LLM_TEMPERATURE", "0.2"))
        self.MAX_TOKENS = int(os.getenv("MAX_TOKENS", "8000"))
        self.MAX_LLM_CALL_RETRIES = int(os.getenv("MAX_LLM_CALL_RETRIES", "3"))
        self.LLM_TOTAL_TIMEOUT = int(os.getenv("LLM_TOTAL_TIMEOUT", "600"))

        # Long-term memory (mem0 + pgvector). Off by default because it needs an
        # embeddings endpoint, which not every OpenAI-compatible provider exposes.
        self.LONG_TERM_MEMORY_ENABLED = _bool_env("LONG_TERM_MEMORY_ENABLED", False)
        self.LONG_TERM_MEMORY_MODEL = os.getenv("LONG_TERM_MEMORY_MODEL", self.DEFAULT_LLM_MODEL)
        self.LONG_TERM_MEMORY_EMBEDDER_MODEL = os.getenv("LONG_TERM_MEMORY_EMBEDDER_MODEL", "text-embedding-3-small")
        self.LONG_TERM_MEMORY_COLLECTION_NAME = os.getenv("LONG_TERM_MEMORY_COLLECTION_NAME", "longterm_memory")

        # JWT auth. The auth router is only mounted when AUTH_ENABLED is true —
        # existing business endpoints never require a token.
        self.AUTH_ENABLED = _bool_env("AUTH_ENABLED", False)
        self.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_ACCESS_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_DAYS", "30"))

        # Logging
        backend_dir = Path(__file__).resolve().parent.parent.parent
        self.LOG_DIR = Path(os.getenv("LOG_DIR", str(backend_dir / "logs")))
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FORMAT = os.getenv("LOG_FORMAT", "console")

        # Postgres — agent framework store only (checkpoints, memory, auth).
        self.POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
        self.POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
        self.POSTGRES_DB = os.getenv("POSTGRES_DB", "job_matcher_agent")
        self.POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
        self.POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
        self.POSTGRES_POOL_SIZE = int(os.getenv("POSTGRES_POOL_SIZE", "10"))
        self.POSTGRES_MAX_OVERFLOW = int(os.getenv("POSTGRES_MAX_OVERFLOW", "5"))
        self.CHECKPOINT_TABLES = ["checkpoint_blobs", "checkpoint_writes", "checkpoints"]

        # Valkey/Redis cache — optional; in-memory fallback when unset.
        self.VALKEY_HOST = os.getenv("VALKEY_HOST", "")
        self.VALKEY_PORT = int(os.getenv("VALKEY_PORT", "6379"))
        self.VALKEY_DB = int(os.getenv("VALKEY_DB", "0"))
        self.VALKEY_PASSWORD = os.getenv("VALKEY_PASSWORD", "")
        self.VALKEY_MAX_CONNECTIONS = int(os.getenv("VALKEY_MAX_CONNECTIONS", "20"))
        self.CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "60"))

        # Rate limiting. These only apply to routes carrying an explicit
        # @limiter.limit() decorator — no SlowAPIMiddleware is installed, so
        # existing business endpoints are untouched.
        self.RATE_LIMIT_DEFAULT = parse_list_from_env("RATE_LIMIT_DEFAULT", ["1000 per day", "200 per hour"])
        default_endpoints = {
            "register": ["10 per hour"],
            "login": ["20 per minute"],
            "session": ["30 per minute"],
        }
        self.RATE_LIMIT_ENDPOINTS = default_endpoints.copy()
        for endpoint in default_endpoints:
            value = parse_list_from_env(f"RATE_LIMIT_{endpoint.upper()}")
            if value:
                self.RATE_LIMIT_ENDPOINTS[endpoint] = value

        self.apply_environment_settings()

    def postgres_url(self, driver: str = "postgresql") -> str:
        """Build a Postgres connection URL for the agent store.

        Args:
            driver: SQLAlchemy/psycopg driver prefix.

        Returns:
            A connection URL with the password URL-encoded.
        """
        from urllib.parse import quote_plus

        user = quote_plus(self.POSTGRES_USER)
        password = quote_plus(self.POSTGRES_PASSWORD)
        return f"{driver}://{user}:{password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    def apply_environment_settings(self) -> None:
        """Apply environment-specific defaults for values not set explicitly."""
        env_settings = {
            Environment.DEVELOPMENT: {
                "DEBUG": True,
                # INFO, not DEBUG: the app's own DEBUG events are few, but the
                # level also governs how much the console shows per line. Set
                # LOG_LEVEL=DEBUG explicitly to get callsites back.
                "LOG_LEVEL": "INFO",
                "LOG_FORMAT": "console",
                "RATE_LIMIT_DEFAULT": ["1000 per day", "200 per hour"],
            },
            Environment.STAGING: {
                "DEBUG": False,
                "LOG_LEVEL": "INFO",
                "RATE_LIMIT_DEFAULT": ["500 per day", "100 per hour"],
            },
            Environment.PRODUCTION: {
                "DEBUG": False,
                "LOG_LEVEL": "WARNING",
                "LOG_FORMAT": "json",
                "RATE_LIMIT_DEFAULT": ["200 per day", "50 per hour"],
            },
            Environment.TEST: {
                "DEBUG": True,
                "LOG_LEVEL": "DEBUG",
                "LOG_FORMAT": "console",
                "RATE_LIMIT_DEFAULT": ["1000 per day", "1000 per hour"],
            },
        }

        for key, value in env_settings.get(self.ENVIRONMENT, {}).items():
            if key.upper() not in os.environ:
                setattr(self, key, value)


settings = Settings()
