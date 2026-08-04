"""Agent framework core.

Ported from the fastapi-langgraph-agent-production-ready-template. This package
holds framework-level infrastructure (settings, logging, metrics, rate limiting,
caching, tracing) that agents in ``app/agents/`` build on top of.

Note the two distinct configuration systems in this backend:

* ``app.config``      — YAML-driven business config (SQLite path, uploads, crawl).
* ``app.core.config`` — env-driven agent framework config (Postgres, Langfuse, JWT).
"""
