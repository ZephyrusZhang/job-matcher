import os
import pytest
from app.config import load_config, _resolve_env_vars


def test_resolve_env_vars():
    os.environ["TEST_VAR"] = "hello"
    assert _resolve_env_vars("${TEST_VAR}") == "hello"
    assert _resolve_env_vars("prefix_${TEST_VAR}_suffix") == "prefix_hello_suffix"
    assert _resolve_env_vars("no_vars_here") == "no_vars_here"
    del os.environ["TEST_VAR"]


def test_resolve_env_vars_missing():
    assert _resolve_env_vars("${NONEXISTENT_VAR}") == ""


def test_load_config():
    config = load_config()
    assert config.server.port == 8000
    assert len(config.companies) == 3
    assert config.companies[0].id == "bytedance"
    assert config.database.path == "data/job_matcher.db"
