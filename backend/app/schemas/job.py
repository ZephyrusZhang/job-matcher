from pydantic import BaseModel


class CompanyBrief(BaseModel):
    id: str
    name: str


class JobOut(BaseModel):
    id: str
    title: str
    category: str
    company: CompanyBrief
    location: list[str] = []
    job_type: str | None = None
    #: 职位描述 and 职位要求, both the site's own text.
    description: str | None = None
    requirements: str | None = None
    posted_date: str | None = None
    source_url: str
    is_favorited: bool = False
    created_at: str
