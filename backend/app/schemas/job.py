from pydantic import BaseModel


class CompanyBrief(BaseModel):
    id: str
    name: str


class Requirements(BaseModel):
    must_have: list[str] = []
    nice_to_have: list[str] = []


class JobOut(BaseModel):
    id: str
    title: str
    category: str
    company: CompanyBrief
    location: str | None = None
    job_type: str | None = None
    responsibilities: str | None = None
    requirements: Requirements
    department: str | None = None
    department_product: str | None = None
    education: str | None = None
    experience: str | None = None
    posted_date: str | None = None
    source_url: str
    summary: str | None = None
    is_favorited: bool = False
    created_at: str
