"""Jobs router — minimal stub for exception middleware testing."""

from fastapi import APIRouter, Request

from app.exceptions import JobNotFoundError

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request):
    db = request.app.state.db
    row = await db.fetch_one("SELECT * FROM jobs WHERE id = ?", (job_id,))
    if row is None:
        raise JobNotFoundError()
    return {"success": True, "data": row, "error": None, "pagination": None}
