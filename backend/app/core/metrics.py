"""Prometheus metrics for the agent framework.

Ported from the fastapi-langgraph-agent template, with the template's
order-processing counters replaced by crawl/agent metrics relevant here.
"""

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
)
from starlette_prometheus import (
    PrometheusMiddleware,
    metrics,
)

# HTTP metrics
http_requests_total = Counter("http_requests_total", "Total number of HTTP requests", ["method", "endpoint", "status"])

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds", ["method", "endpoint"]
)

# LLM metrics
llm_inference_duration_seconds = Histogram(
    "llm_inference_duration_seconds",
    "Time spent processing LLM inference",
    ["model"],
    buckets=[0.1, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

llm_stream_duration_seconds = Histogram(
    "llm_stream_duration_seconds",
    "Time spent processing LLM stream inference",
    ["model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

# Agent metrics
agent_runs_total = Counter(
    "agent_runs_total",
    "Total agent runs",
    ["agent", "status"],  # status: success | cancelled | error
)

agent_run_duration_seconds = Histogram(
    "agent_run_duration_seconds",
    "End-to-end agent run duration",
    ["agent"],
    buckets=[5.0, 15.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0],
)

agent_turns_total = Histogram(
    "agent_turns_total",
    "Number of ReAct turns taken per agent run",
    ["agent"],
    buckets=[1, 2, 4, 8, 16, 32, 64],
)

agent_tool_calls_total = Counter(
    "agent_tool_calls_total",
    "Total agent tool invocations",
    ["agent", "tool", "status"],  # status: success | error
)

agent_tool_duration_seconds = Histogram(
    "agent_tool_duration_seconds",
    "Agent tool execution duration",
    ["agent", "tool"],
    buckets=[0.1, 0.5, 1.0, 5.0, 15.0, 60.0, 300.0],
)

# Crawl metrics
crawl_jobs_found = Gauge("crawl_jobs_found", "Jobs returned by the most recent crawl", ["company"])


def setup_metrics(app) -> None:
    """Install the Prometheus middleware and expose ``/metrics``.

    Args:
        app: The FastAPI application instance.
    """
    app.add_middleware(PrometheusMiddleware)
    app.add_route("/metrics", metrics)
