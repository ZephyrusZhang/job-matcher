from pydantic import BaseModel


class ParsedResume(BaseModel):
    skills: list[str] = []
    experience_years: int | None = None
    education: str | None = None
    raw_text: str = ""


class ClearResult(BaseModel):
    reports_deleted: int = 0
    messages_deleted: int = 0


class ResumeOut(BaseModel):
    id: str
    label: str
    filename: str
    parsed: ParsedResume
    is_default: bool = False
    uploaded_at: str


class ResumeUploadOut(ResumeOut):
    cleared: ClearResult = ClearResult()


class ResumeUpdate(BaseModel):
    label: str | None = None
    is_default: bool | None = None
