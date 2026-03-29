"""Tests for configuration loading."""

import os
from pathlib import Path

import pytest


class TestConfigLoading:
    def test_load_config_from_yaml(self, app_config):
        assert app_config.server.host == "127.0.0.1"
        assert app_config.server.port == 8000
        assert app_config.database.path == ":memory:"

    def test_companies_loaded(self, app_config):
        assert len(app_config.companies) == 2
        assert app_config.companies[0].id == "test_company"
        assert app_config.companies[0].name == "测试公司"
        assert app_config.companies[0].crawl_interval_hours == 24

    def test_llm_config(self, app_config):
        assert app_config.llm.base_url == "http://localhost:11434/v1"
        assert app_config.llm.api_key == "not-needed"
        assert app_config.llm.model == "test-model"
        assert app_config.llm.model_report == "test-model"

    def test_env_var_substitution(self, tmp_path: Path):
        """${ENV_VAR} placeholders should be resolved."""
        os.environ["TEST_LLM_URL"] = "http://my-server:8080/v1"
        settings = tmp_path / "settings.yml"
        settings.write_text(
            """
server:
  host: "0.0.0.0"
  port: 8000
  cors_origins: []
database:
  path: ":memory:"
uploads:
  dir: "/tmp/uploads"
  max_size_mb: 10
  allowed_types: ["application/pdf"]
llm:
  base_url: "${TEST_LLM_URL}"
  api_key: "not-needed"
  model: "qwen2.5"
  model_report: "qwen2.5"
  max_tokens_report: 4096
  max_tokens_chat: 2048
  temperature: 0.7
crawl:
  browser_headless: true
  page_load_timeout: 30000
  max_scroll_attempts: 20
  concurrent_companies: 2
"""
        )
        companies = tmp_path / "companies.yml"
        companies.write_text("companies: []")

        from app.config import load_config

        config = load_config(
            settings_path=settings, companies_path=companies
        )
        assert config.llm.base_url == "http://my-server:8080/v1"
        del os.environ["TEST_LLM_URL"]

    def test_env_var_with_default(self, tmp_path: Path):
        """${VAR:-default} should fall back to default when VAR is unset."""
        settings = tmp_path / "settings.yml"
        settings.write_text(
            """
server:
  host: "0.0.0.0"
  port: 8000
  cors_origins: []
database:
  path: ":memory:"
uploads:
  dir: "/tmp/uploads"
  max_size_mb: 10
  allowed_types: ["application/pdf"]
llm:
  base_url: "${UNSET_VAR:-http://fallback:1234/v1}"
  api_key: "not-needed"
  model: "qwen2.5"
  model_report: "qwen2.5"
  max_tokens_report: 4096
  max_tokens_chat: 2048
  temperature: 0.7
crawl:
  browser_headless: true
  page_load_timeout: 30000
  max_scroll_attempts: 20
  concurrent_companies: 2
"""
        )
        companies = tmp_path / "companies.yml"
        companies.write_text("companies: []")

        from app.config import load_config

        config = load_config(settings_path=settings, companies_path=companies)
        assert config.llm.base_url == "http://fallback:1234/v1"

    def test_upload_config(self, app_config):
        assert app_config.uploads.max_size_mb == 10
        assert "application/pdf" in app_config.uploads.allowed_types

    def test_crawl_config(self, app_config):
        assert app_config.crawl.browser_headless is True
        assert app_config.crawl.max_scroll_attempts == 20
