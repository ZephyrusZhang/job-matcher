from pydantic import BaseModel


class CompanyCreate(BaseModel):
    id: str
    name: str
    career_url: str
    crawl_interval_hours: int = 12


class CompanyUpdate(BaseModel):
    name: str | None = None
    career_url: str | None = None
    crawl_interval_hours: int | None = None


class CompanyOut(BaseModel):
    id: str
    name: str
    career_url: str
    crawl_interval_hours: int
    last_crawled_at: str | None = None
    job_count: int = 0
    crawl_status: str = "idle"  # idle / pending / running / completed / failed
