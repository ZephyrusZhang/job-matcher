from pydantic import BaseModel


class FavoriteCreate(BaseModel):
    job_id: str


class FavoriteOut(BaseModel):
    job_id: str
    favorited_at: str


class FavoriteJobOut(BaseModel):
    job_id: str
    title: str
    category: str
    company_name: str
    location: list[str] = []
    favorited_at: str


class FavoriteSummaryItem(BaseModel):
    company_id: str
    company_name: str
    count: int
