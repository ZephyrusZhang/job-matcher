from pydantic import BaseModel


class CrawlTriggerRequest(BaseModel):
    company_id: str


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
