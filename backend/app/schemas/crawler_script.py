from pydantic import BaseModel


class CrawlerScriptOut(BaseModel):
    company_id: str
    code: str
    updated_at: str


class CrawlerScriptUpdate(BaseModel):
    code: str
