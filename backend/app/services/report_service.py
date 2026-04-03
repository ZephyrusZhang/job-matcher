import json
import uuid
from collections.abc import AsyncGenerator

import aiosqlite

from app.exceptions import NoFavoritesError, ResumeNotFoundError
from app.llm.client import LLMClient
from app.llm.context import ContextManager
from app.llm.prompts import compare, match
from app.models import favorite as fav_model
from app.models import report as report_model
from app.models import resume as resume_model
from app.schemas.report import Preferences, ReportOut


class ReportService:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.context_manager = ContextManager()

    async def generate_report(
        self,
        db: aiosqlite.Connection,
        company_id: str,
        preferences: Preferences,
        report_type: str,
    ) -> AsyncGenerator[str, None]:
        """Generate a match or compare report via SSE streaming.

        Yields SSE-formatted strings.
        """
        # Validate resume exists
        resume_data = await resume_model.get_resume(db)
        if not resume_data:
            raise ResumeNotFoundError()

        # Get favorited jobs for the company
        fav_jobs = await fav_model.get_favorite_jobs_by_company(db, company_id)
        if not fav_jobs:
            raise NoFavoritesError()

        # Delete old report for this company+type (cascade deletes chat)
        await report_model.delete_report(db, company_id, report_type)

        # Prepare context
        parsed_resume = json.dumps(resume_data["parsed_data"], ensure_ascii=False)
        prefs_str = json.dumps(preferences.model_dump(), ensure_ascii=False)
        jobs_str = self.context_manager.format_jobs_for_context(fav_jobs)
        job_ids = [j["id"] for j in fav_jobs]

        # Build messages
        if report_type == "match":
            messages = match.build_messages(parsed_resume, prefs_str, jobs_str)
            start_event = "report_start"
            end_event = "report_end"
        else:
            messages = compare.build_messages(parsed_resume, prefs_str, jobs_str)
            start_event = "compare_start"
            end_event = "compare_end"

        report_id = str(uuid.uuid4())
        full_content = []

        # Start event
        yield f"event: {start_event}\ndata: {json.dumps({'report_id': report_id})}\n\n"

        # Stream chunks
        async for chunk in self.llm_client.stream_generate(messages):
            full_content.append(chunk)
            yield f"event: chunk\ndata: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"

        # Save report to DB
        content = "".join(full_content)
        await report_model.upsert_report(
            db, report_id, company_id, report_type,
            content, job_ids, preferences.model_dump(),
        )

        # End event
        yield f"event: {end_event}\ndata: {json.dumps({'report_id': report_id, 'job_ids': job_ids})}\n\n"

    async def get_report(
        self,
        db: aiosqlite.Connection,
        company_id: str,
        report_type: str,
    ) -> ReportOut | None:
        data = await report_model.get_report(db, company_id, report_type)
        if not data:
            return None
        return ReportOut(
            report_id=data["id"],
            company_id=data["company_id"],
            content=data["content"],
            job_ids=data["job_ids"],
            preferences=Preferences(**data["preferences"]),
            created_at=data["created_at"],
        )
