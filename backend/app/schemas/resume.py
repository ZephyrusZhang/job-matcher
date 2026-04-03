from pydantic import BaseModel


class ParsedResume(BaseModel):
    skills: list[str] = []
    experience_years: int | None = None
    education: str | None = None
    raw_text: str = ""


class ClearResult(BaseModel):
    reports_deleted: int = 0
    messages_deleted: int = 0


class ResumeUploadOut(BaseModel):
    filename: str
    parsed: ParsedResume
    uploaded_at: str
    cleared: ClearResult


class ResumeOut(BaseModel):
    filename: str
    parsed: ParsedResume
    uploaded_at: str
