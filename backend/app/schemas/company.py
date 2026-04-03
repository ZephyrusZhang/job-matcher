from pydantic import BaseModel


class CompanyOut(BaseModel):
    id: str
    name: str
    career_url: str
    crawl_interval_hours: int
    last_crawled_at: str | None = None
    job_count: int = 0
