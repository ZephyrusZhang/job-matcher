from pydantic import BaseModel


class Preferences(BaseModel):
    interest: str
    additional: str = ""


class GenerateRequest(BaseModel):
    company_id: str
    preferences: Preferences


class ReportOut(BaseModel):
    report_id: str
    company_id: str
    content: str
    job_ids: list[str]
    preferences: Preferences
    created_at: str
