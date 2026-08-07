import uuid
from pathlib import Path

import aiosqlite
from fastapi import UploadFile

from app.config import UploadConfig
from app.exceptions import FileFormatError, FileTooLargeError, ResumeNotFoundError
from app.llm.client import LLMClient
from app.llm.prompts import parse_resume
from app.models import resume as resume_model
from app.schemas.resume import ParsedResume, ResumeOut, ResumeUploadOut
from app.utils.file_parser import FileParser

from app.core.logging import get_logger

logger = get_logger(__name__)


class ResumeService:
    def __init__(self, upload_config: UploadConfig, llm_client: LLMClient):
        self.upload_config = upload_config
        self.llm_client = llm_client

    @staticmethod
    def _to_out(data: dict) -> ResumeOut:
        parsed = data["parsed_data"]
        return ResumeOut(
            id=data["id"],
            label=data["label"],
            filename=data["filename"],
            parsed=ParsedResume(**{k: parsed.get(k) for k in ParsedResume.model_fields}),
            is_default=data["is_default"],
            uploaded_at=data["uploaded_at"],
        )

    async def upload(
        self,
        db: aiosqlite.Connection,
        file: UploadFile,
        label: str = "",
        make_default: bool = False,
    ) -> ResumeUploadOut:
        """Store and parse a new resume.

        Args:
            db: Open connection.
            file: Uploaded PDF or DOCX.
            label: Optional display name.
            make_default: Promote the new resume to the default.

        Returns:
            The stored resume.

        Raises:
            FileFormatError: Unsupported extension.
            FileTooLargeError: Above the configured size limit.
        """
        filename = file.filename or "unknown"
        ext = Path(filename).suffix.lower()
        if ext not in (".pdf", ".docx"):
            raise FileFormatError()

        content = await file.read()
        if len(content) > self.upload_config.max_size_mb * 1024 * 1024:
            raise FileTooLargeError()

        upload_dir = Path(self.upload_config.dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        # Unique per resume — resumes used to be a singleton sharing one path.
        file_path = upload_dir / f"resume_{uuid.uuid4().hex[:12]}{ext}"
        file_path.write_bytes(content)

        raw_text = await FileParser.extract_text(str(file_path), filename)

        messages = parse_resume.build_messages(raw_text)
        try:
            parsed = await self.llm_client.structured_parse(messages)
        except Exception:
            logger.warning("LLM resume parsing failed, using raw text only")
            parsed = {"skills": [], "experience_years": None, "education": None}
        parsed["raw_text"] = raw_text

        stored = await resume_model.create_resume(
            db, filename, str(file_path), parsed, label=label, make_default=make_default
        )
        return ResumeUploadOut(**self._to_out(stored).model_dump())

    async def get(self, db: aiosqlite.Connection, resume_id: str | None = None) -> ResumeOut | None:
        """Return one resume, defaulting to the current default."""
        data = await resume_model.get_resume(db, resume_id)
        return self._to_out(data) if data else None

    async def list(self, db: aiosqlite.Connection) -> list[ResumeOut]:
        """Return every stored resume."""
        return [self._to_out(row) for row in await resume_model.list_resumes(db)]

    async def update(
        self,
        db: aiosqlite.Connection,
        resume_id: str,
        label: str | None = None,
        is_default: bool | None = None,
    ) -> ResumeOut:
        """Rename a resume and/or promote it to the default.

        Raises:
            ResumeNotFoundError: When the resume does not exist.
        """
        if not await resume_model.get_resume(db, resume_id):
            raise ResumeNotFoundError()

        if label is not None:
            await resume_model.rename_resume(db, resume_id, label)
        if is_default:
            await resume_model.set_default_resume(db, resume_id)

        return self._to_out(await resume_model.get_resume(db, resume_id))  # type: ignore[arg-type]

    async def delete(self, db: aiosqlite.Connection, resume_id: str | None = None) -> None:
        """Delete a resume and its file.

        Args:
            db: Open connection.
            resume_id: Resume to delete. ``None`` deletes the default.

        Raises:
            ResumeNotFoundError: When the resume does not exist.
        """
        data = await resume_model.get_resume(db, resume_id)
        if not data:
            raise ResumeNotFoundError()

        file_path = Path(data["file_path"])
        if file_path.exists():
            file_path.unlink()

        await resume_model.delete_resume(db, data["id"])
