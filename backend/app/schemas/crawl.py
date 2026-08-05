from typing import Literal

from pydantic import BaseModel

# `agent` rewrites the crawler from scratch; `cached` runs the stored script
# and never falls back, so a caller always gets the run it asked for.
CrawlMode = Literal["agent", "cached"]


class CrawlTriggerRequest(BaseModel):
    company_id: str
    mode: CrawlMode = "agent"


class CrawlTaskOut(BaseModel):
    id: str
    company_id: str
    company_name: str
    status: str
    jobs_found: int = 0
    jobs_new: int = 0
    jobs_updated: int = 0
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str
