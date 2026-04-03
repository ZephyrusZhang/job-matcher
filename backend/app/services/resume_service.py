import logging
from pathlib import Path

import aiosqlite
from fastapi import UploadFile

from app.config import LLMConfig, UploadConfig
from app.exceptions import FileFormatError, FileTooLargeError, ResumeNotFoundError
from app.llm.client import LLMClient
from app.llm.prompts import parse_resume
from app.models import report as report_model
from app.models import resume as resume_model
from app.schemas.resume import ClearResult, ParsedResume, ResumeOut, ResumeUploadOut
from app.utils.file_parser import FileParser

logger = logging.getLogger(__name__)


class ResumeService:
    def __init__(self, upload_config: UploadConfig, llm_client: LLMClient):
        self.upload_config = upload_config
        self.llm_client = llm_client

    async def upload(
        self, db: aiosqlite.Connection, file: UploadFile
    ) -> ResumeUploadOut:
        # Validate format
        filename = file.filename or "unknown"
        ext = Path(filename).suffix.lower()
        if ext not in (".pdf", ".docx"):
            raise FileFormatError()

        # Read and validate size
        content = await file.read()
        max_bytes = self.upload_config.max_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise FileTooLargeError()

        # Save file
        upload_dir = Path(self.upload_config.dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / f"resume{ext}"
        file_path.write_bytes(content)

        # Extract text
        raw_text = await FileParser.extract_text(str(file_path), filename)

        # LLM parse
        messages = parse_resume.build_messages(raw_text)
        try:
            parsed = await self.llm_client.structured_parse(messages)
        except Exception:
            logger.warning("LLM resume parsing failed, using raw text only")
            parsed = {"skills": [], "experience_years": None, "education": None}
        parsed["raw_text"] = raw_text

        # Cascade clear
        reports_deleted, messages_deleted = await report_model.delete_all_reports(db)

        # Upsert resume
        await resume_model.upsert_resume(db, filename, str(file_path), parsed)

        # Get uploaded_at
        resume_data = await resume_model.get_resume(db)
        uploaded_at = resume_data["uploaded_at"] if resume_data else ""

        return ResumeUploadOut(
            filename=filename,
            parsed=ParsedResume(**{k: parsed.get(k) for k in ParsedResume.model_fields}),
            uploaded_at=uploaded_at,
            cleared=ClearResult(
                reports_deleted=reports_deleted,
                messages_deleted=messages_deleted,
            ),
        )

    async def get(self, db: aiosqlite.Connection) -> ResumeOut | None:
        data = await resume_model.get_resume(db)
        if not data:
            return None
        parsed = data["parsed_data"]
        return ResumeOut(
            filename=data["filename"],
            parsed=ParsedResume(**{k: parsed.get(k) for k in ParsedResume.model_fields}),
            uploaded_at=data["uploaded_at"],
        )

    async def delete(self, db: aiosqlite.Connection) -> ClearResult:
        resume_data = await resume_model.get_resume(db)
        if not resume_data:
            raise ResumeNotFoundError()

        # Delete file
        file_path = Path(resume_data["file_path"])
        if file_path.exists():
            file_path.unlink()

        # Cascade clear
        reports_deleted, messages_deleted = await report_model.delete_all_reports(db)
        await resume_model.delete_resume(db)

        return ClearResult(
            reports_deleted=reports_deleted,
            messages_deleted=messages_deleted,
        )
