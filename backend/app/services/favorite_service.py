import aiosqlite

from app.exceptions import JobNotFoundError
from app.models import favorite as fav_model
from app.models import job as job_model
from app.schemas.favorite import FavoriteJobOut, FavoriteOut, FavoriteSummaryItem
from app.services.company_service import CompanyService
from app.services.job_service import _parse_location_field


class FavoriteService:
    def __init__(self, company_service: CompanyService):
        self.company_service = company_service

    async def add_favorite(
        self, db: aiosqlite.Connection, job_id: str
    ) -> FavoriteOut:
        # Check job exists
        job = await job_model.get_job_by_id(db, job_id)
        if not job:
            raise JobNotFoundError()
        created_at = await fav_model.add_favorite(db, job_id)
        return FavoriteOut(job_id=job_id, favorited_at=created_at)

    async def remove_favorite(
        self, db: aiosqlite.Connection, job_id: str
    ) -> None:
        await fav_model.remove_favorite(db, job_id)

    async def get_favorites(
        self, db: aiosqlite.Connection, company_id: str | None = None
    ) -> list[FavoriteJobOut]:
        rows = await fav_model.get_favorites(db, company_id)
        result = []
        for row in rows:
            company_name = self.company_service.get_company_name(row["company_id"]) or row["company_id"]
            result.append(
                FavoriteJobOut(
                    job_id=row["job_id"],
                    title=row["title"],
                    category=row["category"],
                    company_name=company_name,
                    location=_parse_location_field(row.get("location")),
                    favorited_at=row["created_at"],
                )
            )
        return result

    async def get_summary(
        self, db: aiosqlite.Connection
    ) -> list[FavoriteSummaryItem]:
        rows = await fav_model.get_favorites_summary(db)
        result = []
        for row in rows:
            company_name = self.company_service.get_company_name(row["company_id"]) or row["company_id"]
            result.append(
                FavoriteSummaryItem(
                    company_id=row["company_id"],
                    company_name=company_name,
                    count=row["count"],
                )
            )
        return result
